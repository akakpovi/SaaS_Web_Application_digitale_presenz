// frontend/src/components/UpgradeBanner.tsx

import React from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { X, Rocket } from 'lucide-react';

interface UpgradeBannerProps {
    usedSites: number;
    maxSites: number;
    onDismiss: () => void;
}

export const UpgradeBanner: React.FC<UpgradeBannerProps> = ({
    usedSites,
    maxSites,
    onDismiss,
}) => {
    const { t, i18n } = useTranslation();
    const usagePercentage = (usedSites / maxSites) * 100;

    if (usagePercentage < 30) return null;

    return (
        <div className="relative bg-gradient-to-r from-indigo-50 to-blue-50 dark:from-indigo-900/20 dark:to-blue-900/20 border border-indigo-200 dark:border-indigo-800 rounded-xl p-4">
            <button
                onClick={onDismiss}
                className="absolute top-2 right-2 text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300"
            >
                <X size={18} />
            </button>

            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                <div className="flex-1">
                    <div className="flex items-center gap-2">
                        <Rocket size={20} className="text-indigo-600 dark:text-indigo-400" />
                        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                            {t('upgrade.title', { used: usedSites, max: maxSites })}
                        </h3>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                        {t('upgrade.description')}
                    </p>
                    <div className="w-full max-w-xs h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full mt-2 overflow-hidden">
                        <div
                            className={`h-full rounded-full transition-all ${usagePercentage >= 80 ? 'bg-red-500' :
                                    usagePercentage >= 50 ? 'bg-yellow-500' :
                                        'bg-indigo-500'
                                }`}
                            style={{ width: `${Math.min(usagePercentage, 100)}%` }}
                        />
                    </div>
                </div>

                <Link
                    to={`/${i18n.language}/pricing`}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium whitespace-nowrap transition-colors"
                >
                    {t('upgrade.cta')} →
                </Link>
            </div>
        </div>
    );
};