import { useEffect, useState } from 'react';
import type { Api } from '../api/client';
import type { Health } from '../api/types';

export type WakeState = 'checking' | 'waking' | 'ready' | 'down';

export interface Wake {
  state: WakeState;
  health: Health | null;
}

export const WAKE_BANNER_AFTER_MS = 3000;
const RETRY_EVERY_MS = 3000;
const GIVE_UP_AFTER_MS = 90_000;

/**
 * Pings /health. Free hosting sleeps when idle, so if the first answer takes longer than
 * `bannerAfterMs`, or fails (a sleeping host often answers with an error), the state becomes
 * "waking" until the server responds (or we give up).
 */
export function useServerWake(api: Api, bannerAfterMs = WAKE_BANNER_AFTER_MS): Wake {
  const [wake, setWake] = useState<Wake>({ state: 'checking', health: null });

  useEffect(() => {
    const controller = new AbortController();
    const started = Date.now();
    let retryTimer: ReturnType<typeof setTimeout> | undefined;

    const bannerTimer = setTimeout(() => {
      setWake((w) => (w.state === 'checking' ? { ...w, state: 'waking' } : w));
    }, bannerAfterMs);

    const attempt = () => {
      api
        .health(controller.signal)
        .then((health) => {
          clearTimeout(bannerTimer);
          setWake({ state: 'ready', health });
        })
        .catch((error: unknown) => {
          if (controller.signal.aborted) return;
          if (error instanceof DOMException && error.name === 'AbortError') return;
          if (Date.now() - started > GIVE_UP_AFTER_MS) {
            clearTimeout(bannerTimer);
            setWake({ state: 'down', health: null });
            return;
          }
          setWake((w) => ({ ...w, state: 'waking' }));
          retryTimer = setTimeout(attempt, RETRY_EVERY_MS);
        });
    };
    attempt();

    return () => {
      controller.abort();
      clearTimeout(bannerTimer);
      clearTimeout(retryTimer);
    };
  }, [api, bannerAfterMs]);

  return wake;
}
