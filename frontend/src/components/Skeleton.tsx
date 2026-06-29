interface SkeletonProps {
  className?: string
}

export default function Skeleton({ className = '' }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-slate-700/30 ${className}`}
      style={{ background: 'var(--bg-secondary-alpha)' }}
    />
  )
}
