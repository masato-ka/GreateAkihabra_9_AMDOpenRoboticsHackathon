import React from 'react'
import './DonutIcon.css'

interface DonutIconProps {
  type: 'chocolate' | 'strawberry'
  size?: 'small' | 'medium' | 'large'
}

const DonutIcon: React.FC<DonutIconProps> = ({ type, size = 'medium' }) => {
  const color = type === 'chocolate' ? '#8B4513' : '#FF69B4'
  const sizeClass = `donut-icon-${size}`
  
  return (
    <div className={`donut-icon ${sizeClass}`}>
      <svg
        viewBox="0 0 100 100"
        xmlns="http://www.w3.org/2000/svg"
        className="donut-svg"
      >
        {/* ドーナッツ本体 */}
        <circle
          cx="50"
          cy="50"
          r="40"
          fill="none"
          stroke={color}
          strokeWidth="4"
        />
        <circle
          cx="50"
          cy="50"
          r="15"
          fill="none"
          stroke={color}
          strokeWidth="4"
        />
        
        {/* サングラス */}
        <rect x="35" y="40" width="10" height="7" fill={color} rx="2" />
        <rect x="55" y="40" width="10" height="7" fill={color} rx="2" />
        <line
          x1="45"
          y1="43.5"
          x2="55"
          y2="43.5"
          stroke={color}
          strokeWidth="2.5"
        />
        
        {/* 笑顔 */}
        <path
          d="M 40 60 Q 50 72 60 60"
          stroke={color}
          strokeWidth="3"
          fill="none"
          strokeLinecap="round"
        />
        
        {/* トッピング */}
        {type === 'chocolate' ? (
          <>
            {/* チョコチップ */}
            <circle cx="30" cy="30" r="3" fill={color} />
            <circle cx="70" cy="30" r="3" fill={color} />
            <circle cx="25" cy="50" r="2.5" fill={color} />
            <circle cx="75" cy="50" r="2.5" fill={color} />
            <circle cx="30" cy="70" r="3" fill={color} />
            <circle cx="70" cy="70" r="3" fill={color} />
          </>
        ) : (
          <>
            {/* イチゴの種 */}
            <circle cx="30" cy="30" r="1.5" fill={color} />
            <circle cx="70" cy="30" r="1.5" fill={color} />
            <circle cx="25" cy="50" r="1.5" fill={color} />
            <circle cx="75" cy="50" r="1.5" fill={color} />
            <circle cx="30" cy="70" r="1.5" fill={color} />
            <circle cx="70" cy="70" r="1.5" fill={color} />
            {/* イチゴの葉っぱ */}
            <path
              d="M 50 20 Q 45 15 40 20 Q 45 18 50 20 Q 55 18 60 20 Q 55 15 50 20"
              fill={color}
              opacity="0.6"
            />
          </>
        )}
      </svg>
    </div>
  )
}

export default DonutIcon

