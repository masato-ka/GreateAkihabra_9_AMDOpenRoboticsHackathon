import React from 'react'
import './CompleteIcon.css'

const CompleteIcon: React.FC = () => {
  return (
    <div className="complete-icon-container">
      <svg
        viewBox="0 0 100 100"
        xmlns="http://www.w3.org/2000/svg"
        className="complete-svg"
      >
        {/* ドーナッツ */}
        <circle cx="50" cy="50" r="40" fill="none" stroke="#dc143c" strokeWidth="4" />
        <circle cx="50" cy="50" r="15" fill="none" stroke="#dc143c" strokeWidth="4" />
        
        {/* サングラス */}
        <rect x="35" y="40" width="10" height="7" fill="#dc143c" rx="2" />
        <rect x="55" y="40" width="10" height="7" fill="#dc143c" rx="2" />
        <line x1="45" y1="43.5" x2="55" y2="43.5" stroke="#dc143c" strokeWidth="2.5" />
        
        {/* 笑顔 */}
        <path d="M 40 60 Q 50 72 60 60" stroke="#dc143c" strokeWidth="3" fill="none" strokeLinecap="round" />
        
        {/* チェックマーク */}
        <path
          d="M 30 50 L 45 65 L 70 35"
          stroke="#4CAF50"
          strokeWidth="6"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        
        {/* スプリンクル */}
        <circle cx="25" cy="30" r="2" fill="#dc143c" />
        <circle cx="75" cy="30" r="2" fill="#dc143c" />
        <circle cx="20" cy="50" r="1.5" fill="#dc143c" />
        <circle cx="80" cy="50" r="1.5" fill="#dc143c" />
        <circle cx="25" cy="70" r="2" fill="#dc143c" />
        <circle cx="75" cy="70" r="2" fill="#dc143c" />
      </svg>
    </div>
  )
}

export default CompleteIcon

