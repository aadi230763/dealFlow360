import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function base(children: React.ReactNode, props: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      width={16}
      height={16}
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export function SunIcon(props: IconProps) {
  return base(
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </>,
    props,
  );
}

export function MoonIcon(props: IconProps) {
  return base(<path d="M20.5 14.5A8.5 8.5 0 1 1 9.5 3.5a7 7 0 0 0 11 11Z" />, props);
}

export function CloseIcon(props: IconProps) {
  return base(
    <>
      <path d="M18 6 6 18" />
      <path d="M6 6l12 12" />
    </>,
    props,
  );
}

export function ChevronDownIcon(props: IconProps) {
  return base(<path d="m6 9 6 6 6-6" />, props);
}

export function BellIcon(props: IconProps) {
  return base(
    <>
      <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </>,
    props,
  );
}

export function MenuIcon(props: IconProps) {
  return base(
    <>
      <path d="M4 6h16" />
      <path d="M4 12h16" />
      <path d="M4 18h16" />
    </>,
    props,
  );
}

export function CheckCircleIcon(props: IconProps) {
  return base(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m8.5 12.5 2.5 2.5 4.5-5" />
    </>,
    props,
  );
}

export function AlertCircleIcon(props: IconProps) {
  return base(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v5" />
      <path d="M12 16h.01" />
    </>,
    props,
  );
}

export function InboxIcon(props: IconProps) {
  return base(
    <>
      <path d="M4 4h16l-1.5 10H5.5L4 4Z" />
      <path d="M4 14h4.5a2 2 0 0 0 1.9 1.4h3.2A2 2 0 0 0 15.5 14H20" />
      <path d="M4 14v6h16v-6" />
    </>,
    props,
  );
}

export function EyeIcon(props: IconProps) {
  return base(
    <>
      <path d="M1.5 12S5 5 12 5s10.5 7 10.5 7-3.5 7-10.5 7S1.5 12 1.5 12Z" />
      <circle cx="12" cy="12" r="3" />
    </>,
    props,
  );
}

export function EyeOffIcon(props: IconProps) {
  return base(
    <>
      <path d="M17.94 17.94A10.94 10.94 0 0 1 12 19c-7 0-10.5-7-10.5-7a19.12 19.12 0 0 1 4.22-5.06M9.9 4.24A10.4 10.4 0 0 1 12 5c7 0 10.5 7 10.5 7a19.2 19.2 0 0 1-2.16 3.19M14.12 14.12a3 3 0 1 1-4.24-4.24" />
      <path d="M1 1l22 22" />
    </>,
    props,
  );
}
