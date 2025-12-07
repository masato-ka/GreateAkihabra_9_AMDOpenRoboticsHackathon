import React from 'react'
import './Logo.css'
import logoImage from '../img/Logo.jpg'

const Logo: React.FC = () => {
  return (
    <div className="logo-container">
      <img src={logoImage} alt="GreatAkihabara Donuts" className="logo-image" />
    </div>
  )
}

export default Logo
