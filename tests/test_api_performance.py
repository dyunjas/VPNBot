import os
os.environ["LUNET_TESTING"]="1"
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import AsyncMock
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from backend.database.models import Base,User,Transaction,Subscription,SubscriptionPlan,SubStatus
from backend.services.dashboard_stats import dashboard_totals
from backend.services.subscription_service import SubscriptionService
from backend.repositories.transaction_repository import TransactionRepository

class ApiPerformanceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine=create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
        self.statements=[]
        event.listen(self.engine.sync_engine,"before_cursor_execute",lambda conn,cursor,statement,parameters,context,many:self.statements.append(statement))
        self.session=async_sessionmaker(self.engine,expire_on_commit=False)()
        self.now=datetime(2026,10,17,12,tzinfo=timezone.utc)
        self.session.add_all([User(id=1,tg_id=101,balance=10,banned=False,created_at=self.now),User(id=2,tg_id=102,balance=20,banned=True,created_at=self.now-timedelta(days=10))])
        self.session.add_all([SubscriptionPlan(id=i,name=f"Plan {i}",price=100,purchase_limit=1) for i in range(1,21)])
        for i in range(1,76):self.session.add(Transaction(id=i,user_id=1 if i<=70 else 2,transaction_id=str(i),amount=100,payment_system="test",paid=i%2==0,paid_at=self.now if i%2==0 else None,created_at=self.now))
        self.session.add_all([
            Subscription(user_id=1,plan_id=1,status=SubStatus.active,current_period_end=self.now+timedelta(days=7)),
            Subscription(user_id=1,plan_id=1,status=SubStatus.active,current_period_end=self.now+timedelta(days=8)),
            Subscription(user_id=2,plan_id=1,status=SubStatus.active,current_period_end=self.now),
            Subscription(user_id=2,plan_id=2,status=SubStatus.expired,current_period_end=self.now+timedelta(days=2))])
        await self.session.commit();self.statements.clear()
    async def asyncTearDown(self):await self.session.close();await self.engine.dispose()
    async def test_dashboard_totals_in_three_round_trips(self):
        result=await dashboard_totals(self.session,self.now)
        self.assertEqual(len(self.statements),3)
        self.assertEqual(result,{"total_users":2,"banned_users":1,"new_users_today":1,"total_balance":30,"unpaid_transactions":38,"paid_transactions":37,"total_revenue":3700,"today_revenue":3700,"month_revenue":3700,"active_subscriptions":2,"subscribed_users":1,"expiring_subscriptions":1})
    async def test_history_limit_and_account_isolation(self):
        rows=await TransactionRepository(self.session).list_by_user_id(1,limit=50)
        self.assertEqual([row.id for row in rows],list(range(70,20,-1)))
        self.assertTrue(all(row.user_id==1 for row in rows))
        self.assertIn("LIMIT",self.statements[-1])
        self.assertEqual(len(await TransactionRepository(self.session).list_by_user_id(1)),70)
    async def test_plan_limit_checks_use_one_grouped_query(self):
        visible=await SubscriptionService(self.session).list_plans()
        self.assertEqual(len(visible),18)
        self.assertNotIn(1,[p.id for p in visible]);self.assertNotIn(2,[p.id for p in visible])
        reads=[s for s in self.statements if s.lstrip().upper().startswith("SELECT")]
        self.assertEqual(len(reads),2,"20 limited plans should use 2 reads, not 21")
        self.assertIn("GROUP BY",reads[1])
    async def test_reads_avoid_locks_but_mutations_keep_them(self):
        service=SubscriptionService(self.session)
        service.user_repo.get_by_id=AsyncMock(return_value=object())
        service.user_repo.get_by_id_for_update=AsyncMock(return_value=object())
        service.sub_repo.get_active_with_plan=AsyncMock(return_value=object())
        await service.get_active_subscription(1,for_update=False)
        service.user_repo.get_by_id.assert_awaited_once_with(1)
        service.user_repo.get_by_id_for_update.assert_not_awaited()
        await service.get_active_subscription(1)
        service.user_repo.get_by_id_for_update.assert_awaited_once_with(1)
    async def test_empty_dashboard(self):
        empty=create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with empty.begin() as conn:await conn.run_sync(Base.metadata.create_all)
            async with async_sessionmaker(empty)() as session:self.assertTrue(all(v==0 for v in (await dashboard_totals(session,self.now)).values()))
        finally:await empty.dispose()
if __name__=="__main__":unittest.main()
