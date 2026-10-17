import os
os.environ["LUNET_TESTING"] = "1"

import logging
import unittest
from unittest.mock import patch

import httpx
from fastapi import FastAPI, HTTPException, Request

from backend.core.incidents import Event, IncidentBuffer, category, fingerprint, redact, render
from backend.core.error_reporter import TelegramErrorReportHandler, _trim_report
from backend.apps.common import apply_common_hardening


def event(kind="network", key="timeout", created=1700000000, peer=""):
    return Event(kind,key,"API","service.py:20","Request timeout",peer=peer,created=created)


class IncidentTests(unittest.TestCase):
    def test_network_burst_is_one_digest_with_correct_count(self):
        buffer=IncidentBuffer(now=0)
        for n in range(80):self.assertEqual(buffer.add(event(created=1700000000+n),n),[])
        self.assertEqual(buffer.flush(119),([],0))
        incidents,overflow=buffer.flush(120)
        self.assertEqual(len(incidents),1)
        self.assertEqual(incidents[0].count,80)
        self.assertEqual(overflow,0)
        caption,report=render(incidents)
        self.assertIn("80",caption)
        self.assertIn("UTC",report)
        self.assertEqual(buffer.flush(240),([],0))

    def test_critical_first_is_immediate_repeats_wait_for_cooldown(self):
        buffer=IncidentBuffer(now=0)
        self.assertEqual(buffer.add(event("critical"),1)[0].count,1)
        for n in range(2,10):self.assertEqual(buffer.add(event("critical"),n),[])
        self.assertEqual(buffer.flush(120),([],0))
        self.assertEqual(buffer.flush(240),([],0))
        repeated,_=buffer.flush(360)
        self.assertEqual(repeated[0].count,8)
        self.assertIn("КРИТИЧЕСКИЙ",render(repeated)[0])

    def test_many_unique_criticals_are_limited_to_three_immediate_alerts(self):
        buffer=IncidentBuffer(now=0)
        immediate=[]
        for n in range(20):immediate.extend(buffer.add(event("critical",str(n)),n))
        self.assertEqual(len(immediate),3)
        digest,_=buffer.flush(120)
        self.assertEqual(sum(i.count for i in digest),17)

    def test_security_ip_variation_is_grouped_and_memory_is_bounded(self):
        buffer=IncidentBuffer(max_groups=10,now=0)
        for n in range(1000):buffer.add(event("security","admin",peer=f"10.0.0.{n}"),n/100)
        self.assertEqual(len(buffer.groups["admin"].peers),5)
        for n in range(30):buffer.add(event("error",str(n)),20)
        self.assertEqual(len(buffer.groups),10)
        items,overflow=buffer.flush(120)
        self.assertEqual(overflow,21)
        self.assertEqual(next(i.count for i in items if i.event.kind=="security"),1000)

    def test_network_and_explicit_critical_classification(self):
        record=logging.makeLogRecord({"msg":"request failed","levelno":logging.ERROR,"exc_info":(TimeoutError,TimeoutError("timeout"),None)})
        self.assertEqual(category(record,record.msg),"network")
        record.levelno=logging.CRITICAL
        self.assertEqual(category(record,record.msg),"critical")
        record.levelno=logging.ERROR
        self.assertEqual(category(record,"Database connection failed"),"critical")

    def test_fingerprints_ignore_volatile_ids_and_addresses(self):
        self.assertEqual(fingerprint("error","API","s.py","user=123 peer=1.2.3.4"),fingerprint("error","API","s.py","user=456 peer=5.6.7.8"))
        self.assertNotEqual(fingerprint("error","API","s.py","decode failed"),fingerprint("error","API","s.py","database failed"))

    def test_secret_redaction_applies_to_messages_and_tracebacks(self):
        raw='password="secret with spaces" initData=telegram-data https://user:dbpass@host/a?token=querysecret Bearer access-secret /bot123456:abcdefghijklmnopqrstuvw/sendMessage'
        text=redact(raw)
        for secret in ("secret with spaces","telegram-data","dbpass","querysecret","access-secret","abcdefghijklmnopqrstuvw"):
            self.assertNotIn(secret,text)
        handler=TelegramErrorReportHandler(start_worker=False)
        try:
            handler.emit(logging.makeLogRecord({"msg":raw,"levelno":logging.ERROR,"pathname":"service.py","lineno":4}))
            frozen=handler._queue.get_nowait()
            self.assertNotIn("telegram-data",frozen.message)
            self.assertNotIn("dbpass",frozen.message)
        finally:handler.close()

    def test_handler_ignores_ordinary_warnings_and_its_own_failures(self):
        handler=TelegramErrorReportHandler(start_worker=False)
        try:
            handler.emit(logging.makeLogRecord({"msg":"warning","levelno":logging.WARNING}))
            handler.emit(logging.makeLogRecord({"msg":"own failure","levelno":logging.ERROR,"telegram_error_report_skip":True}))
            self.assertTrue(handler._queue.empty())
            handler.emit(logging.makeLogRecord({"msg":"denied","levelno":logging.WARNING,"security_event":True}))
            self.assertEqual(handler._queue.get_nowait().kind,"security")
        finally:handler.close()

    def test_truncated_report_is_valid_utf8_within_limit(self):
        result=_trim_report("Ошибка\n"*2000,1024)
        self.assertLessEqual(len(result),1024)
        self.assertIn("truncated",result.decode("utf-8"))


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_transport_uses_one_document_and_distinguishes_critical_alert(self):
        captured=[]
        class Reply:
            status=200
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            async def json(self,**kwargs):return {"ok":True}
        class Session:
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            def post(self,url,*,data,proxy):
                captured.append({field[0]["name"]:field[2] for field in data._fields})
                return Reply()
        handler=TelegramErrorReportHandler(start_worker=False)
        try:
            with patch("backend.core.error_reporter._error_report_settings",return_value=("test-token",1,2,32000,None)),patch("backend.core.error_reporter.aiohttp.ClientSession",return_value=Session()):
                buffer=IncidentBuffer(now=0)
                for n in range(10):buffer.add(event(),n)
                digest,overflow=buffer.flush(120)
                await handler._send_report(digest,overflow)
                await handler._send_report(buffer.add(event("critical","fatal"),121))
            self.assertEqual(len(captured),2)
            self.assertEqual(captured[0]["disable_notification"],"true")
            self.assertIn("10",captured[0]["caption"])
            self.assertEqual(captured[1]["disable_notification"],"false")
            self.assertIn("<b>🚨 КРИТИЧЕСКИЙ",captured[1]["caption"])
            self.assertEqual(captured[0]["message_thread_id"],"2")
        finally:handler.close()


class SecurityMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app=FastAPI()
        apply_common_hardening(self.app)

        @self.app.api_route("/api/admin/users/{user_id}",methods=["GET","POST"])
        async def denied(user_id:str):raise HTTPException(403,"denied")

        @self.app.get("/api/admin/auth/me")
        async def session():raise HTTPException(401,"expired")

        @self.app.post("/api/admin/auth/login")
        async def login():raise HTTPException(401,"invalid credentials")

        @self.app.post("/api/payments/platega-webhook")
        async def webhook():raise HTTPException(403,"invalid signature")

        @self.app.post("/api/admin/expected-reauth")
        async def reauth(request:Request):
            request.state.admin_auth={"_reauthentication_required":True}
            raise HTTPException(403,"reauth needed")

        @self.app.get("/api/admin/allowed")
        async def allowed():return {"ok":True}

        @self.app.get("/api/admin/proxy")
        async def proxy(request:Request):
            request.state.is_api_proxy=True
            raise HTTPException(403,"upstream already reported")

        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url="https://test")

    async def asyncTearDown(self):await self.client.aclose()

    async def test_denied_access_has_route_status_and_peer_without_secrets(self):
        with self.assertLogs("vpn.security",logging.WARNING) as captured:
            response=await self.client.get("/api/admin/users/123?token=secret",headers={"Authorization":"Bearer hidden","X-Forwarded-For":"attacker-controlled"})
        self.assertEqual(response.status_code,403)
        record=captured.records[0]
        self.assertIn("/api/admin/users/{user_id}",record.getMessage())
        self.assertNotIn("secret",record.getMessage())
        self.assertNotIn("hidden",record.getMessage())
        self.assertEqual(record.security_peer,"127.0.0.1")

    async def test_failed_login_webhook_and_probe_are_observed(self):
        with self.assertLogs("vpn.security",logging.WARNING) as captured:
            await self.client.post("/api/admin/auth/login",json={"password":"secret"})
            await self.client.post("/api/payments/platega-webhook")
            await self.client.get("/.env")
        self.assertEqual(len(captured.records),3)
        self.assertNotIn("secret"," ".join(captured.output))

    async def test_normal_session_checks_success_reauth_and_proxy_are_quiet(self):
        with patch("backend.core.security_events.log.warning") as warning:
            await self.client.get("/api/admin/auth/me")
            await self.client.get("/api/admin/allowed")
            await self.client.post("/api/admin/expected-reauth")
            await self.client.get("/api/admin/proxy")
            warning.assert_not_called()

    async def test_rejected_large_payload_is_observed_before_endpoint(self):
        with self.assertLogs("vpn.security",logging.WARNING) as captured:
            response=await self.client.post("/api/admin/users/123",content=b"x",headers={"Content-Length":str(2*1024*1024)})
        self.assertEqual(response.status_code,413)
        self.assertIn("HTTP 413",captured.output[0])


if __name__=="__main__":unittest.main()
