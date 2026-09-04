import { NavLink, Route, Routes } from 'react-router'
import { CallCenterPage } from './CallCenterPage'
import { CompliancePage } from './CompliancePage'
import { LiveKitVoice } from './LiveKitVoice'
import { Icon } from './components/Icon'

export function App() {
  return (
    <LiveKitVoice>
      <div className="appShell">
        <aside className="sidebar">
          <div className="brand">
            <span>A</span>
            <div>
              <b>ASACI</b>
              <small>Contact intelligent</small>
            </div>
          </div>
          <nav aria-label="Navigation principale">
            <NavLink to="/">
              <Icon name="headset" />
              <span>Console d’appel</span>
            </NavLink>
            <NavLink to="/conformite">
              <Icon name="shield" />
              <span>Conformité</span>
            </NavLink>
          </nav>
          <div className="sidebarFoot">
            <span className="statusDot" />
            Services opérationnels<small>Environnement de démonstration</small>
          </div>
        </aside>
        <div className="appContent">
          <header className="topbar">
            <div>
              <span className="eyebrow">ESPACE CONSEILLER</span>
              <strong>Agent vocal conversationnel</strong>
            </div>
            <div className="secureBadge">
              <Icon name="shield" size={16} />
              <span>Mode sécurisé</span>
            </div>
          </header>
          <Routes>
            <Route path="/" element={<CallCenterPage />} />
            <Route path="/conformite" element={<CompliancePage />} />
            <Route path="*" element={<CallCenterPage />} />
          </Routes>
        </div>
      </div>
    </LiveKitVoice>
  )
}
