import { useTranslation } from 'react-i18next';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  label?: string;
  fullScreen?: boolean;
}

export function LoadingSpinner({ size = 'md', label, fullScreen = false }: LoadingSpinnerProps) {
  const { t } = useTranslation();
  
  const sizes = {
    sm: 'h-5 w-5 border-2',
    md: 'h-8 w-8 border-3',
    lg: 'h-12 w-12 border-4',
    xl: 'h-16 w-16 border-4',
  };

  const containerClasses = fullScreen 
    ? 'fixed inset-0 z-50 flex items-center justify-center bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm'
    : 'flex flex-col items-center justify-center gap-3 p-4';

  return (
    <div className={containerClasses}>
      <div className="relative">
        {/* Anneau principal */}
        <div className={`${sizes[size]} animate-spin rounded-full border-indigo-600 border-t-transparent`} />
        
        {/* Anneau secondaire (effet de vague) */}
        <div className={`absolute inset-0 ${sizes[size]} animate-pulse rounded-full border-2 border-indigo-400/30 border-t-transparent`} />
        
        {/* Points lumineux */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="flex gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-600 animate-bounce [animation-delay:-0.3s]" />
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-600 animate-bounce [animation-delay:-0.15s]" />
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-600 animate-bounce" />
          </div>
        </div>
      </div>
      
      {label && (
        <p className="text-sm font-medium text-gray-600 dark:text-gray-300 animate-pulse">
          {label}
        </p>
      )}
    </div>
  );
}

export default LoadingSpinner;
