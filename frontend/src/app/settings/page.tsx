'use client';

import { useState } from 'react';

export default function SettingsPage() {
  const [settings, setSettings] = useState({
    slackIntegration: true,
    slackWebhookUrl: 'https://hooks.slack.com/services/TXXXXXX/BXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXX',
    stalePrThreshold: 7,
    notifyOnNewPr: true,
    notifyOnChangesRequested: true,
    notifyOnStalePr: true,
    timezone: 'UTC'
  });

  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    const checked = type === 'checkbox' ? (e.target as HTMLInputElement).checked : undefined;
    
    setSettings(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    
    // Simulate API call
    setTimeout(() => {
      setIsSaving(false);
      setSaveSuccess(true);
      
      // Hide success message after 3 seconds
      setTimeout(() => {
        setSaveSuccess(false);
      }, 3000);
    }, 1000);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Settings</h1>
        <p className="text-gray-600">Configure your Prequel application</p>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800">Notification Settings</h2>
        </div>
        
        <div className="p-6">
          <form onSubmit={handleSubmit}>
            {/* Slack Integration */}
            <div className="mb-6">
              <div className="flex items-center">
                <input
                  id="slackIntegration"
                  name="slackIntegration"
                  type="checkbox"
                  checked={settings.slackIntegration}
                  onChange={handleChange}
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <label htmlFor="slackIntegration" className="ml-2 block text-sm font-medium text-gray-700">
                  Enable Slack Integration
                </label>
              </div>
              <p className="mt-1 text-sm text-gray-500">
                Receive notifications in your Slack workspace
              </p>
            </div>

            {/* Slack Webhook URL */}
            {settings.slackIntegration && (
              <div className="mb-6">
                <label htmlFor="slackWebhookUrl" className="block text-sm font-medium text-gray-700">
                  Slack Webhook URL
                </label>
                <div className="mt-1">
                  <input
                    type="text"
                    name="slackWebhookUrl"
                    id="slackWebhookUrl"
                    value={settings.slackWebhookUrl}
                    onChange={handleChange}
                    className="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md"
                  />
                </div>
                <p className="mt-1 text-sm text-gray-500">
                  Get this URL from your Slack app settings
                </p>
              </div>
            )}

            {/* Stale PR Threshold */}
            <div className="mb-6">
              <label htmlFor="stalePrThreshold" className="block text-sm font-medium text-gray-700">
                Stale PR Threshold (days)
              </label>
              <div className="mt-1">
                <input
                  type="number"
                  name="stalePrThreshold"
                  id="stalePrThreshold"
                  min="1"
                  max="30"
                  value={settings.stalePrThreshold}
                  onChange={handleChange}
                  className="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md"
                />
              </div>
              <p className="mt-1 text-sm text-gray-500">
                Number of days of inactivity before a PR is considered stale
              </p>
            </div>

            {/* Notification Settings */}
            <div className="mb-6">
              <h3 className="text-sm font-medium text-gray-700 mb-3">Notification Events</h3>
              <div className="space-y-2">
                <div className="flex items-center">
                  <input
                    id="notifyOnNewPr"
                    name="notifyOnNewPr"
                    type="checkbox"
                    checked={settings.notifyOnNewPr}
                    onChange={handleChange}
                    className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                  />
                  <label htmlFor="notifyOnNewPr" className="ml-2 block text-sm text-gray-700">
                    New Pull Requests
                  </label>
                </div>
                <div className="flex items-center">
                  <input
                    id="notifyOnChangesRequested"
                    name="notifyOnChangesRequested"
                    type="checkbox"
                    checked={settings.notifyOnChangesRequested}
                    onChange={handleChange}
                    className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                  />
                  <label htmlFor="notifyOnChangesRequested" className="ml-2 block text-sm text-gray-700">
                    Changes Requested
                  </label>
                </div>
                <div className="flex items-center">
                  <input
                    id="notifyOnStalePr"
                    name="notifyOnStalePr"
                    type="checkbox"
                    checked={settings.notifyOnStalePr}
                    onChange={handleChange}
                    className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                  />
                  <label htmlFor="notifyOnStalePr" className="ml-2 block text-sm text-gray-700">
                    Stale Pull Requests
                  </label>
                </div>
              </div>
            </div>

            {/* Timezone */}
            <div className="mb-6">
              <label htmlFor="timezone" className="block text-sm font-medium text-gray-700">
                Timezone
              </label>
              <select
                id="timezone"
                name="timezone"
                value={settings.timezone}
                onChange={handleChange}
                className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
              >
                <option value="UTC">UTC</option>
                <option value="America/New_York">Eastern Time (ET)</option>
                <option value="America/Chicago">Central Time (CT)</option>
                <option value="America/Denver">Mountain Time (MT)</option>
                <option value="America/Los_Angeles">Pacific Time (PT)</option>
                <option value="Europe/London">London</option>
                <option value="Europe/Paris">Paris</option>
                <option value="Asia/Tokyo">Tokyo</option>
              </select>
              <p className="mt-1 text-sm text-gray-500">
                Used for displaying dates and scheduling notifications
              </p>
            </div>

            {/* Save Button */}
            <div className="flex justify-end">
              {saveSuccess && (
                <span className="mr-4 text-sm text-green-600 self-center">
                  Settings saved successfully!
                </span>
              )}
              <button
                type="submit"
                disabled={isSaving}
                className={`px-4 py-2 ${
                  isSaving ? 'bg-indigo-400' : 'bg-indigo-600 hover:bg-indigo-700'
                } text-white rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500`}
              >
                {isSaving ? 'Saving...' : 'Save Settings'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}