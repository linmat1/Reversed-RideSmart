import React from 'react';
import './MaintenancePage.css';

function MaintenancePage() {
  return (
    <div className="maintenance-page">
      <div className="maintenance-container">
        <div className="maintenance-icon">🔧</div>
        <h1>Under Maintenance</h1>
        <p className="maintenance-message">
          too buggy rn, too many people getting no-shows, working on fixing, should be back in like TODAY OR TOMORROW
        </p>
        <div className="maintenance-contact">
          <p className="contact-info">+447754666843 on WhatsApp</p>
        </div>
      </div>
    </div>
  );
}

export default MaintenancePage;
