import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Utility to merge Tailwind classes with proper precedence
 * Uses clsx for conditional classes and tailwind-merge to resolve conflicts
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Type for className props - supports single string or object with multiple keys
 */
export type ClassName = ClassValue;
export type ClassNameRecord<T extends string> = Partial<Record<T, ClassValue>>;
