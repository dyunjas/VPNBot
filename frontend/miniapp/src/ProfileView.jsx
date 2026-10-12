import { Wallet } from "lucide-react";
import { Card, money } from "../../shared/account/components.jsx";
import { ProfileSummary } from "./ProfileSummary.jsx";

export function Profile({user,profile}) {
  return <div className="view-stack"><div><h1 className="page-heading">Мой профиль</h1><p className="page-description">Данные аккаунта и реферальная программа.</p></div><ProfileSummary user={user}/><Card><span className="feature-icon"><Wallet size={22}/></span><h2>Реферальная программа</h2><div className="detail-list"><div><span className="detail-label">Приглашено</span><b>{profile?.referral?.invited_count||0}</b></div><div><span className="detail-label">Реферальный баланс</span><b>{money(profile?.referral?.balance)} ₽</b></div></div></Card></div>;
}
