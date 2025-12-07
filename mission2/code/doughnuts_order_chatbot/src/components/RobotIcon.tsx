import React from 'react'
import './RobotIcon.css'

const RobotIcon: React.FC = () => {
  return (
    <div className="robot-icon-container">
      <svg
        viewBox="0 0 120 140"
        xmlns="http://www.w3.org/2000/svg"
        className="robot-svg"
      >
        {/* ロボット本体 */}
        <rect x="30" y="40" width="60" height="70" rx="8" fill="#dc143c" />
        
        {/* ロボットの頭 */}
        <rect x="40" y="20" width="40" height="30" rx="5" fill="#dc143c" />
        
        {/* 目 */}
        <circle cx="52" cy="32" r="4" fill="white" />
        <circle cx="68" cy="32" r="4" fill="white" />
        
        {/* アンテナ */}
        <line x1="60" y1="20" x2="60" y2="10" stroke="#dc143c" strokeWidth="3" strokeLinecap="round" />
        <circle cx="60" cy="8" r="3" fill="#dc143c" />
        
        {/* ロボットアーム（左） */}
        <rect x="15" y="50" width="15" height="8" rx="4" fill="#dc143c" />
        <rect x="10" y="58" width="8" height="25" rx="4" fill="#dc143c" />
        <rect x="5" y="80" width="12" height="8" rx="4" fill="#dc143c" />
        
        {/* ロボットアーム（右） */}
        <rect x="90" y="50" width="15" height="8" rx="4" fill="#dc143c" />
        <rect x="102" y="58" width="8" height="25" rx="4" fill="#dc143c" />
        <rect x="103" y="80" width="12" height="8" rx="4" fill="#dc143c" />
        
        {/* ボタン */}
        <circle cx="50" cy="60" r="3" fill="white" />
        <circle cx="70" cy="60" r="3" fill="white" />
        <circle cx="50" cy="75" r="3" fill="white" />
        <circle cx="70" cy="75" r="3" fill="white" />
        
        {/* ドーナッツ（手に持っている） */}
        <circle cx="8" cy="88" r="12" fill="none" stroke="#dc143c" strokeWidth="2" />
        <circle cx="8" cy="88" r="5" fill="none" stroke="#dc143c" strokeWidth="2" />
        <circle cx="5" cy="85" r="1.5" fill="#dc143c" />
        <circle cx="11" cy="85" r="1.5" fill="#dc143c" />
        <path d="M 3 90 Q 8 95 13 90" stroke="#dc143c" strokeWidth="1.5" fill="none" />
      </svg>
    </div>
  )
}

export default RobotIcon

