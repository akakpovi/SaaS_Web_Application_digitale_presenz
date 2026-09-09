// frontend/src/components/ActionRequired.tsx

import React from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, ChevronRight } from 'lucide-react';

interface ActionRequiredProps {
    alerts: number;
    issuesCount: number;
    onViewAll: () => void;
}

export const ActionRequired: React.FC<ActionRequiredProps> = ({
    alerts,
    issuesCount,
    onViewAll,
}) => {
    const { t } = useTranslation();

    return (
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4 animate-pulse-once">
            <div className="flex items-start gap-3">
                <div className="flex-shrink-0">
                    <div className="w-10 h-10 bg-amber-100 dark:bg-amber-900/50 rounded-full flex items-center justify-center">
                        <AlertTriangle size={20} className="text-amber-600 dark:text-amber-400" />
                    </div>
                </div>

                <div className="flex-1">
                    <h3 className="text-sm font-semibold text-amber-800 dark:text-amber-200">
                        {alerts > 0
                            ? t('alerts.critical_count', { count: alerts })
                            : t('alerts.issues_count', { count: issuesCount })}
                    </h3>
                    <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">
                        {t('alerts.action_required_message')}
                    </p>
                    <button
                        onClick={onViewAll}
                        className="mt-2 text-sm font-medium text-amber-700 dark:text-amber-300 hover:text-amber-800 dark:hover:text-amber-200 flex items-center gap-1"
                    >
                        {t('alerts.view_all')}
                        <ChevronRight size={16} />
                    </button>
                </div>
            </div>
        </div>
    );
};