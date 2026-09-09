interface SkeletonLoaderProps {
  type?: 'card' | 'list' | 'table' | 'dashboard';
  count?: number;
}

export function SkeletonLoader({ type = 'card', count = 3 }: SkeletonLoaderProps) {
  const renderCard = () => (
    <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-5 animate-pulse">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded mb-2" />
          <div className="h-5 w-32 bg-gray-200 dark:bg-gray-700 rounded mb-2" />
          <div className="h-3 w-48 bg-gray-200 dark:bg-gray-700 rounded" />
        </div>
        <div className="h-10 w-16 bg-gray-200 dark:bg-gray-700 rounded-lg" />
      </div>
      <div className="mt-4 pt-3 border-t border-gray-100 dark:border-gray-700">
        <div className="flex justify-between">
          <div className="h-3 w-20 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="h-3 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
        </div>
      </div>
    </div>
  );

  const renderDashboard = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-5 animate-pulse">
            <div className="h-3 w-20 bg-gray-200 dark:bg-gray-700 rounded mb-2" />
            <div className="h-8 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => renderCard())}
      </div>
    </div>
  );

  const renderList = () => (
    <div className="space-y-3">
      {[...Array(count)].map((_, i) => (
        <div key={i} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 animate-pulse">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 bg-gray-200 dark:bg-gray-700 rounded-full" />
            <div className="flex-1">
              <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded mb-2" />
              <div className="h-3 w-48 bg-gray-200 dark:bg-gray-700 rounded" />
            </div>
            <div className="h-8 w-20 bg-gray-200 dark:bg-gray-700 rounded" />
          </div>
        </div>
      ))}
    </div>
  );

  const renderTable = () => (
    <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 overflow-hidden animate-pulse">
      <div className="p-4 border-b border-gray-100 dark:border-gray-700">
        <div className="h-5 w-32 bg-gray-200 dark:bg-gray-700 rounded" />
      </div>
      <div className="divide-y divide-gray-100 dark:divide-gray-700">
        {[...Array(count)].map((_, i) => (
          <div key={i} className="p-4 flex items-center gap-4">
            <div className="h-4 w-4 bg-gray-200 dark:bg-gray-700 rounded" />
            <div className="flex-1 h-4 bg-gray-200 dark:bg-gray-700 rounded" />
            <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded" />
            <div className="h-4 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
          </div>
        ))}
      </div>
    </div>
  );

  switch (type) {
    case 'dashboard': return renderDashboard();
    case 'list': return renderList();
    case 'table': return renderTable();
    default: return renderCard();
  }
}

export default SkeletonLoader;
