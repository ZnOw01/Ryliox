import { LayoutGroup, motion, MotionConfig } from 'framer-motion';
import { useId, type ReactNode } from 'react';

type AnimatedLayoutGroupProps = {
  children: ReactNode;
  id?: string;
  className?: string;
};

export function AnimatedLayoutGroup({ children, id, className = '' }: AnimatedLayoutGroupProps) {
  const generatedId = useId();

  return (
    <MotionConfig reducedMotion="user">
      <LayoutGroup id={id || generatedId}>
        <div className={className}>{children}</div>
      </LayoutGroup>
    </MotionConfig>
  );
}

type StaggeredLayoutContainerProps = {
  children: ReactNode;
  className?: string;
};

// Kept as a compatibility wrapper, without cumulative list delays.
export function StaggeredLayoutContainer({
  children,
  className = '',
}: StaggeredLayoutContainerProps) {
  return <div className={className}>{children}</div>;
}

type StaggeredLayoutItemProps = {
  children: ReactNode;
  className?: string;
  layoutId?: string;
};

export function StaggeredLayoutItem({
  children,
  className = '',
  layoutId,
}: StaggeredLayoutItemProps) {
  return (
    <motion.div
      className={className}
      layout="position"
      layoutId={layoutId}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.15 }}
    >
      {children}
    </motion.div>
  );
}
