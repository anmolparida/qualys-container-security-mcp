interface SkeletonProps {
  className?: string
}

export default function Skeleton({ className = '' }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-[var(--bg-secondary)] ${className}`}
      style={{ background: 'var(--bg-secondary-alpha)' }}
    />
  )
}
