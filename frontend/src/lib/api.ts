// src/lib/api.ts
import axios from 'axios';

// Define base URL for API
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001';

// Create axios instance
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Set a reasonable timeout to avoid long waiting times
  timeout: 5000
});

// Define interfaces for our data models
export interface Repository {
  id: number;
  github_id: number;
  name: string;
  full_name: string;
  created_at: string;
  pr_count: number;
  review_count: number;
  stale_pr_count: number;
  contributor_count: number;
  last_activity: string;
}

export interface Contributor {
  id: number;
  github_id: number;
  username: string;
  avatar_url: string;
  created_at: string;
  pr_count: number;
  review_count: number;
  command_count: number;
  repositories: string[];
}

export interface User {
  id: number;
  github_id: number;
  username: string;
  avatar_url: string;
  created_at: string;
}

export interface PullRequest {
  id: number;
  github_id: number;
  repository_id: number;
  author_id: number;
  title: string;
  number: number;
  state: string;
  html_url: string;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  merged_at: string | null;
  is_stale: boolean;
  last_activity_at: string;
  repository_name?: string;
  author_name?: string;
}

export interface Review {
  id: number;
  github_id: number;
  pull_request_id: number;
  reviewer_id: number;
  state: string;
  submitted_at: string;
  reviewer_name?: string;
}

export interface ReviewComment {
  id: number;
  github_id: number;
  review_id: number | null;
  pull_request_id: number;
  author_id: number;
  body: string;
  created_at: string;
  updated_at: string;
  contains_command: boolean;
  command_type: string | null;
  author_name?: string;
}

export interface PRMetrics {
    pr_authors: [string, number][];
    active_reviewers: [string, number][];
    comment_users: [string, number][];  
    stale_pr_count: number;
}

// Mock data for when API is not available
const mockData = {

  prMetrics: {
    pr_authors: [['user1', 12] as [string, number], ['user2', 8] as [string, number], ['user3', 6] as [string, number], ['user4', 5] as [string, number], ['user5', 4] as [string, number]],
    active_reviewers: [['reviewer1', 15] as [string, number], ['reviewer2', 12] as [string, number], ['reviewer3', 9] as [string, number], ['reviewer4', 7] as [string, number], ['reviewer5', 5] as [string, number]],
    comment_users: [['user2', 10] as [string, number], ['user1', 9] as [string, number], ['user3', 7] as [string, number], ['user5', 6] as [string, number], ['user4', 5] as [string, number]],  // Changed from command_users
    stale_pr_count: 3
  },
  pullRequests: [
    {
      id: 1,
      github_id: 12345,
      repository_id: 1,
      author_id: 1,
      title: "Add new feature to dashboard",
      number: 42,
      state: "open",
      html_url: "https://github.com/org/repo/pull/42",
      created_at: "2023-03-15T10:00:00Z",
      updated_at: "2023-03-20T15:30:00Z",
      closed_at: null,
      merged_at: null,
      is_stale: true,
      last_activity_at: "2023-03-20T15:30:00Z",
      repository_name: "org/repo",
      author_name: "developer1"
    },
    {
      id: 2,
      github_id: 12346,
      repository_id: 1,
      author_id: 2,
      title: "Fix critical bug in authentication",
      number: 43,
      state: "open",
      html_url: "https://github.com/org/repo/pull/43",
      created_at: "2023-03-10T09:15:00Z",
      updated_at: "2023-03-12T14:20:00Z",
      closed_at: null,
      merged_at: null,
      is_stale: true,
      last_activity_at: "2023-03-12T14:20:00Z",
      repository_name: "org/repo",
      author_name: "developer2"
    }
  ],
  repositories: [
    {
      id: 1,
      github_id: 12345,
      name: 'api-service',
      full_name: 'organization/api-service',
      created_at: '2023-01-15T10:00:00Z',
      pr_count: 24,
      review_count: 48,
      stale_pr_count: 2,
      contributor_count: 5,
      last_activity: '2023-04-01T14:30:00Z'
    },
    {
      id: 2,
      github_id: 12346,
      name: 'frontend',
      full_name: 'organization/frontend',
      created_at: '2023-01-20T10:00:00Z',
      pr_count: 36,
      review_count: 72,
      stale_pr_count: 1,
      contributor_count: 8,
      last_activity: '2023-04-02T10:15:00Z'
    }
  ],
  contributors: [
    {
      id: 1,
      github_id: 1001,
      username: 'developer1',
      avatar_url: 'https://api.dicebear.com/7.x/avataaars/svg?seed=developer1',
      created_at: '2023-01-10T10:00:00Z',
      pr_count: 24,
      review_count: 36,
      command_count: 8,
      repositories: ['api-service', 'frontend', 'core-lib']
    },
    {
      id: 2,
      github_id: 1002,
      username: 'developer2',
      avatar_url: 'https://api.dicebear.com/7.x/avataaars/svg?seed=developer2',
      created_at: '2023-01-12T10:00:00Z',
      pr_count: 18,
      review_count: 42,
      command_count: 12,
      repositories: ['frontend', 'docs']
    }
  ]
};

// API functions for data fetching
export const api = {
  // Health check
  healthCheck: async () => {
    try {
      const response = await apiClient.get('/');
      return response.data;
    } catch (error) {
      console.warn('Backend API not available, using mock data');
      return { status: 'healthy (mock)', timestamp: new Date().toISOString() };
    }
  },
  
  // Get PR metrics data for dashboard
  getPRMetrics: async (): Promise<PRMetrics> => {
    try {
      const response = await apiClient.get('/api/metrics');
      return response.data;
    } catch (error) {
      console.warn('Error fetching PR metrics, using mock data');
      // Return mock data instead of empty arrays
      return mockData.prMetrics;
    }
  },
  
  // Get stale PRs
  getStalePRs: async (): Promise<PullRequest[]> => {
    try {
      const response = await apiClient.get('/api/stale-prs');
      return response.data;
    } catch (error) {
      console.warn('Error fetching stale PRs, using mock data');
      return mockData.pullRequests.filter(pr => pr.is_stale);
    }
  },
  
  // Get repositories with metrics
  getRepositories: async (): Promise<Repository[]> => {
    try {
      const response = await apiClient.get('/api/repositories');
      return response.data;
    } catch (error) {
      console.warn('Error fetching repositories, using mock data');
      return mockData.repositories;
    }
  },

  // Get contributors with metrics
  getContributors: async (): Promise<Contributor[]> => {
    try {
      const response = await apiClient.get('/api/contributors');
      return response.data;
    } catch (error) {
      console.warn('Error fetching contributors, using mock data');
      return mockData.contributors;
    }
  },
  
  // Get pull requests with repository and author info
  getPullRequests: async (): Promise<PullRequest[]> => {
    try {
      const response = await apiClient.get('/api/pull-requests');
      return response.data;
    } catch (error) {
      console.warn('Error fetching pull requests, using mock data');
      return mockData.pullRequests;
    }
  }
};

export default api;