import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { BookOpen, ImageBroken, Spinner } from '@phosphor-icons/react';
import { cn } from '../../lib/cn';

interface BookCoverProps {
  src?: string | null;
  alt: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  aspectRatio?: 'book' | 'square' | 'video';
  showPlaceholderText?: boolean;
  placeholderText?: string;
  onLoad?: () => void;
  onError?: () => void;
}

const sizeMap = {
  sm: { width: 48, height: 72 },
  md: { width: 64, height: 96 },
  lg: { width: 80, height: 120 },
  xl: { width: 120, height: 180 },
};

const aspectRatioMap = {
  book: 'aspect-[2/3]',
  square: 'aspect-square',
  video: 'aspect-video',
};

export function BookCover({
  src,
  alt,
  size = 'md',
  className,
  aspectRatio = 'book',
  showPlaceholderText = true,
  placeholderText,
  onLoad,
  onError,
}: BookCoverProps) {
  const [imageState, setImageState] = useState<'loading' | 'loaded' | 'error'>('loading');
  const dimensions = sizeMap[size];

  const handleLoad = useCallback(() => {
    setImageState('loaded');
    onLoad?.();
  }, [onLoad]);

  const handleError = useCallback(() => {
    setImageState('error');
    onError?.();
  }, [onError]);

  const isPlaceholder = !src || imageState === 'error';

  return (
    <motion.div
      className={cn(
        'relative overflow-hidden rounded-lg border border-border bg-muted shadow-sm',
        aspectRatioMap[aspectRatio],
        className
      )}
      style={{
        width: dimensions.width,
        height: dimensions.height,
      }}
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2 }}
    >
      {src && imageState !== 'error' && (
        <motion.img
          src={src}
          alt={alt}
          width={dimensions.width}
          height={dimensions.height}
          className={cn(
            'h-full w-full object-cover transition-all duration-300',
            imageState === 'loaded' ? 'opacity-100' : 'opacity-0'
          )}
          loading="lazy"
          decoding="async"
          onLoad={handleLoad}
          onError={handleError}
          whileHover={{ scale: 1.05 }}
          transition={{ duration: 0.3 }}
        />
      )}

      {imageState === 'loading' && src && (
        <div className="absolute inset-0 flex items-center justify-center bg-muted">
          <Spinner className="h-5 w-5 animate-spin text-muted-foreground" weight="regular" />
        </div>
      )}

      {isPlaceholder && (
        <motion.div
          className="flex h-full w-full flex-col items-center justify-center gap-2 bg-muted p-2 text-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
        >
          {imageState === 'error' ? (
            <ImageBroken
              className="h-6 w-6 text-muted-foreground"
              weight="regular"
              aria-hidden="true"
            />
          ) : (
            <BookOpen
              className="h-6 w-6 text-muted-foreground"
              weight="regular"
              aria-hidden="true"
            />
          )}
          {showPlaceholderText && (
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground leading-tight">
              {imageState === 'error' ? placeholderText || 'Error' : placeholderText || 'No Cover'}
            </span>
          )}
        </motion.div>
      )}
    </motion.div>
  );
}

interface BookCoverSkeletonProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  aspectRatio?: 'book' | 'square' | 'video';
}

export function BookCoverSkeleton({
  size = 'md',
  className,
  aspectRatio = 'book',
}: BookCoverSkeletonProps) {
  const dimensions = sizeMap[size];

  return (
    <div
      className={cn(
        'animate-pulse overflow-hidden rounded-lg border border-border bg-muted',
        aspectRatioMap[aspectRatio],
        className
      )}
      style={{
        width: dimensions.width,
        height: dimensions.height,
      }}
      aria-hidden="true"
    >
      <div className="h-full w-full bg-muted-foreground/20" />
    </div>
  );
}

export default BookCover;
