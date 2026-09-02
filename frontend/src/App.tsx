import { NavLink, Route, Routes } from 'react-router'
import { CallCenterPage } from './CallCenterPage'
import { CompliancePage } from './CompliancePage'
import { LiveKitVoice } from './LiveKitVoice'

export function App(){return <LiveKitVoice>
  <header className="topbar"><div className="brand"><span>A</span><div><b>ASACI Contact</b><small>POC — données fictives uniquement</small></div></div><nav><NavLink to="/">Console</NavLink><NavLink to="/conformite">Conformité</NavLink></nav><div className="online"><i/>Mode sécurisé</div></header>
  <Routes><Route path="/" element={<CallCenterPage/>}/><Route path="/conformite" element={<CompliancePage/>}/><Route path="*" element={<CallCenterPage/>}/></Routes>
</LiveKitVoice>}
