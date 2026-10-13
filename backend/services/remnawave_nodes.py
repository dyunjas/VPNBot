from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID

import aiohttp
from fastapi import HTTPException

from backend.services.remnawave_service import RemnaWaveService


class RemnawaveNodesService:
    """Node administration through documented Remnawave endpoints only."""
    fields = ("uuid", "name", "address", "port", "countryCode", "isConnected", "isDisabled", "isConnecting", "lastStatusChange", "lastStatusMessage", "xrayVersion", "nodeVersion", "xrayUptime", "usersOnline", "trafficUsedBytes", "trafficLimitBytes", "isTrafficTrackingActive", "cpuCount", "cpuModel", "totalRam", "tags", "note", "viewPosition", "trafficResetDay", "notifyPercent", "consumptionMultiplier", "nodeConsumptionMultiplier")
    actions = {"enable":"enable", "disable":"disable", "restart":"restart", "force_restart":"restart", "reset_traffic":"reset-traffic"}

    def __init__(self):
        self.remote = RemnaWaveService(None)

    async def request(self, method: str, path: str, body: dict | None = None):
        if not self.remote.enabled:
            raise HTTPException(503, "Настройте REMNAWAVE_BASE_URL и REMNAWAVE_API_TOKEN для управления нодами.")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as client:
                async with client.request(method, f"{self.remote.base_url}/api{path}", headers=self.remote._headers(), json=body, allow_redirects=False) as response:
                    if response.status in {401,403}:
                        raise HTTPException(502, "Remnawave отказал в доступе. Проверьте API-токен и его права на ноды и метрики.")
                    if response.status == 404:
                        raise HTTPException(404, "Нода или метод API недоступны в установленной версии Remnawave.")
                    if not 200 <= response.status < 300:
                        raise HTTPException(502, f"Remnawave не выполнил запрос (HTTP {response.status}).")
                    raw = await response.read()
                    if not raw:
                        return {}
                    try:
                        return self.remote._unwrap_response(json.loads(raw))
                    except (ValueError,TypeError):
                        raise HTTPException(502, "Remnawave вернул некорректный ответ. Проверьте доступ к API через защиту панели.")
        except (aiohttp.ClientError, asyncio.TimeoutError):
            # Never repeat commands: a timeout does not prove that they failed.
            raise HTTPException(502, "Не удалось получить ответ Remnawave. Обновите состояние ноды перед повтором команды.")

    async def list_nodes(self):
        nodes = await self.request("GET", "/nodes")
        if not isinstance(nodes,list):
            raise HTTPException(502,"Remnawave вернул неподдерживаемый список нод.")
        warnings = []
        async def optional(path, label):
            try: return await self.request("GET",path)
            except HTTPException:
                warnings.append(f"{label} недоступны. Проверьте версию панели и права API-токена.")
                return {}
        metrics, panel = await asyncio.gather(optional("/system/nodes/metrics","Метрики нод"),optional("/system/stats","Показатели панели"))
        metric_rows = metrics.get("nodes",[]) if isinstance(metrics,dict) else []
        metrics_by_uuid = {str(item.get("nodeUuid")):item for item in metric_rows if isinstance(item,dict)}
        items = []
        for node in nodes:
            if not isinstance(node,dict): continue
            item = {key:node.get(key) for key in self.fields}
            profile = node.get("configProfile") or {}
            item["configProfile"] = {"activeConfigProfileUuid":profile.get("activeConfigProfileUuid"), "activeInbounds":[{"uuid":inbound.get("uuid"),"tag":inbound.get("tag")} for inbound in profile.get("activeInbounds",[]) if isinstance(inbound,dict)]}
            metric = metrics_by_uuid.get(str(node.get("uuid")))
            if metric:
                item["usersOnline"] = metric.get("usersOnline",node.get("usersOnline"))
                item["inboundsStats"] = metric.get("inboundsStats",[])
                item["outboundsStats"] = metric.get("outboundsStats",[])
            else:
                item["inboundsStats"], item["outboundsStats"] = [], []
            items.append(item)
        # System memory/CPU describe the PANEL, not the individual VPS nodes.
        panel = panel if isinstance(panel,dict) else {}
        return {"ok":True,"items":items,"warnings":warnings,"checked_at":datetime.now(timezone.utc).isoformat(),"panel":{"cpu":panel.get("cpu"),"memory":panel.get("memory"),"uptime":panel.get("uptime"),"onlineStats":panel.get("onlineStats")}}

    async def action(self, uuid: UUID, action: str):
        if action == "delete":
            await self.request("DELETE",f"/nodes/{uuid}")
            return {"ok":True,"message":"Сервер удалён из панели Remnawave."}
        operation = self.actions.get(action)
        if not operation:
            raise HTTPException(400,"Неизвестная команда ноды")
        body = {"forceRestart":action=="force_restart"} if operation=="restart" else None
        result = await self.request("POST",f"/nodes/{uuid}/actions/{operation}",body)
        if isinstance(result,dict) and result.get("eventSent") is False:
            raise HTTPException(502,"Remnawave не принял команду. Обновите состояние ноды.")
        return {"ok":True,"action":action,"uuid":str(uuid),"message":"Команда отправлена. Статус обновится автоматически."}

    async def save_node(self, body: dict, uuid: UUID | None = None):
        if uuid:body={**body,"uuid":str(uuid)}
        await self.request("PATCH" if uuid else "POST","/nodes",body)
        return {"ok":True,"message":"Настройки сохранены." if uuid else "Сервер добавлен в Remnawave."}

    async def bulk_action(self, uuids: list[UUID], action: str):
        mapped={"enable":"ENABLE","disable":"DISABLE","restart":"RESTART","reset_traffic":"RESET_TRAFFIC"}
        if action not in mapped:raise HTTPException(400,"Неизвестная массовая команда")
        result=await self.request("POST","/nodes/bulk-actions",{"uuids":list(dict.fromkeys(str(uuid) for uuid in uuids)),"action":mapped[action]})
        if isinstance(result,dict) and result.get("eventSent") is False:raise HTTPException(502,"Remnawave не принял команду.")
        return {"ok":True,"message":"Команда отправлена выбранным серверам."}

    async def restart_all(self, force: bool):
        result=await self.request("POST","/nodes/actions/restart-all",{"forceRestart":force})
        if isinstance(result,dict) and result.get("eventSent") is False:raise HTTPException(502,"Remnawave не принял команду.")
        return {"ok":True,"message":"Перезапуск всех включённых серверов запрошен."}

    async def profiles(self):
        data=await self.request("GET","/config-profiles")
        rows=data.get("configProfiles",[]) if isinstance(data,dict) else data if isinstance(data,list) else []
        return {"items":[{"uuid":row.get("uuid"),"name":row.get("name")} for row in rows if isinstance(row,dict)]}

    async def inbounds(self, uuid: UUID):
        data=await self.request("GET",f"/config-profiles/{uuid}/inbounds")
        rows=data.get("inbounds",[]) if isinstance(data,dict) else []
        return {"items":[{key:row.get(key) for key in ("uuid","tag","type","network","security")} for row in rows if isinstance(row,dict)]}
