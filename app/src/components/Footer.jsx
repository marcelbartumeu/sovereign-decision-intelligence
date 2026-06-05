import { useState, useEffect } from 'react';

export default function Footer() {
  const [time, setTime] = useState('');

  useEffect(() => {
    const tick = () => setTime(new Date().toLocaleTimeString());
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="footer">
      <div className="container">
        <div className="footer-content">
          <p>© 2024 Analytics Division</p>
          <p>Data refresh: Live • Last update: <span>{time}</span></p>
        </div>
      </div>
    </div>
  );
}
