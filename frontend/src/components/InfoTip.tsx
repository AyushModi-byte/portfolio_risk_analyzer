import { useId, useState, type KeyboardEvent } from 'react';

interface InfoTipProps {
  /** What the tip explains, used in the button's accessible name. */
  topic: string;
  children: string;
}

/** A small "i" button that shows a plain-language explanation on hover, focus or tap. */
export function InfoTip({ topic, children }: InfoTipProps) {
  const id = useId();
  const [pinned, setPinned] = useState(false);
  const [hovered, setHovered] = useState(false);
  const open = pinned || hovered;

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'Escape') {
      setPinned(false);
      setHovered(false);
    }
  };

  return (
    <span
      className="infotip"
      onMouseEnter={() => {
        setHovered(true);
      }}
      onMouseLeave={() => {
        setHovered(false);
      }}
    >
      <button
        type="button"
        className="infotip-button"
        aria-label={`What is ${topic}?`}
        aria-describedby={id}
        aria-expanded={open}
        onClick={() => {
          setPinned((p) => !p);
        }}
        onBlur={() => {
          setPinned(false);
        }}
        onKeyDown={onKeyDown}
      >
        i
      </button>
      <span role="tooltip" id={id} className="infotip-bubble" hidden={!open}>
        {children}
      </span>
    </span>
  );
}
