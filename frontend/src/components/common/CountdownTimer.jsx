import React, { useState, useEffect, useRef } from 'react';
import { Clock, ShieldAlert } from 'lucide-react';

export default function CountdownTimer({ expiresAt, onExpire, expiredLabel = 'SESSION EXPIRED' }) {
  const [timeLeft, setTimeLeft] = useState(0);
  const onExpireRef = useRef(onExpire);
  const hasExpiredRef = useRef(false);

  useEffect(() => {
    onExpireRef.current = onExpire;
  }, [onExpire]);

  useEffect(() => {
    if (!expiresAt) return;

    const targetTime = new Date(expiresAt).getTime();
    const initialDiff = Math.max(0, Math.floor((targetTime - Date.now()) / 1000));
    setTimeLeft(initialDiff);

    // If already expired at mount, mark as expired without triggering infinite refresh
    if (initialDiff <= 0) {
      hasExpiredRef.current = true;
      return;
    }

    hasExpiredRef.current = false;

    const updateTimer = () => {
      const now = Date.now();
      const diff = Math.max(0, Math.floor((targetTime - now) / 1000));
      setTimeLeft(diff);

      if (diff <= 0) {
        if (!hasExpiredRef.current) {
          hasExpiredRef.current = true;
          if (onExpireRef.current) {
            onExpireRef.current();
          }
        }
      }
    };

    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, [expiresAt]);

  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;

  const isWarning = timeLeft < 180 && timeLeft > 0;
  const isExpired = timeLeft === 0;

  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.5rem',
      padding: '0.4rem 0.85rem',
      background: isExpired
        ? 'rgba(239, 68, 68, 0.15)'
        : isWarning
        ? 'rgba(245, 158, 11, 0.15)'
        : 'rgba(99, 102, 241, 0.15)',
      border: `1px solid ${
        isExpired
          ? 'rgba(239, 68, 68, 0.3)'
          : isWarning
          ? 'rgba(245, 158, 11, 0.3)'
          : 'rgba(99, 102, 241, 0.3)'
      }`,
      borderRadius: '9999px',
      color: isExpired ? '#f87171' : isWarning ? '#fbbf24' : '#818cf8',
      fontSize: '0.88rem',
      fontWeight: 700,
    }}>
      {isExpired ? (
        <>
          <ShieldAlert size={16} />
          <span>{expiredLabel}</span>
        </>
      ) : (
        <>
          <Clock size={16} />
          <span>
            Expires in: {String(minutes).padStart(2, '0')}:{String(seconds).padStart(2, '0')}
          </span>
        </>
      )}
    </div>
  );
}
