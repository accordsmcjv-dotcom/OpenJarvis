export interface AgentScheduleSource {
  config?: Record<string, unknown> | null;
  // Retained as fallbacks for compatibility with older API responses.
  schedule_type?: unknown;
  schedule_value?: unknown;
}

export interface AgentSchedule {
  type?: string;
  value?: string;
}

export interface AgentScheduleConfig {
  type: string;
  value: string;
}

const DEFAULT_DAILY_CRON = '0 9 * * *';
const DEFAULT_WEEKLY_CRON = '0 9 * * 1';
const DEFAULT_HOURLY_SECONDS = '3600';

function isPositiveInterval(value: string): boolean {
  const seconds = Number(value);
  return value.length > 0 && Number.isFinite(seconds) && seconds > 0;
}

function isDailyCron(value: string): boolean {
  return /^0\s+(?:[0-9]|1[0-9]|2[0-3])\s+\*\s+\*\s+\*$/.test(value);
}

function isWeeklyCron(value: string): boolean {
  return /^0\s+(?:[0-9]|1[0-9]|2[0-3])\s+\*\s+\*\s+[1-7](?:,[1-7])*$/.test(value);
}

function scheduleValue(value: unknown): string | undefined {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return undefined;
}

/** Read schedule fields from the managed-agent API response. */
export function getAgentSchedule(agent: AgentScheduleSource): AgentSchedule {
  const nestedType = agent.config?.schedule_type;

  return {
    type:
      typeof nestedType === 'string'
        ? nestedType
        : scheduleValue(agent.schedule_type),
    value:
      scheduleValue(agent.config?.schedule_value) ??
      scheduleValue(agent.schedule_value),
  };
}

/** Convert the launch wizard's friendly presets to a valid API schedule. */
export function normalizeAgentSchedule(type: string, value: unknown): AgentScheduleConfig {
  const current = scheduleValue(value)?.trim() ?? '';

  switch (type) {
    case 'manual':
      return { type: 'manual', value: '' };
    case 'daily':
      return {
        type: 'cron',
        value: isDailyCron(current) ? current : DEFAULT_DAILY_CRON,
      };
    case 'weekly':
      return {
        type: 'cron',
        value: isWeeklyCron(current) ? current : DEFAULT_WEEKLY_CRON,
      };
    case 'hourly':
    case 'interval':
      return {
        type: 'interval',
        value: isPositiveInterval(current) ? current : DEFAULT_HOURLY_SECONDS,
      };
    case 'cron':
      return { type: 'cron', value: current };
    default:
      return { type, value: current };
  }
}

/**
 * Add a predictable plan/execute/verify protocol to managed agents.
 * High-impact external actions remain approval-gated; safe read-only steps
 * can be completed autonomously.
 */
export function buildAgentExecutionInstruction(instruction: string): string {
  const protocol = [
    'WORKFLOW EXECUTION PROTOCOL:',
    '1. Break the request into ordered, small steps and identify dependencies before acting.',
    '2. Execute independent read-only steps autonomously; do not ask the user to approve routine inspection or research.',
    '3. Before sending messages, publishing, deleting, purchasing, changing account/device settings, or sharing private data, pause and obtain explicit user approval.',
    '4. After each meaningful step, record a concise checkpoint with its result and any remaining work.',
    '5. If a step fails, diagnose the cause, retry at most once when safe, then re-plan around the failure instead of claiming success.',
    '6. Verify the final result using available tools and clearly separate completed actions, pending approvals, and blockers.',
    '7. Never invent tool results, files, confirmations, or completed actions.'
  ].join('\\n');
  const userInstruction = instruction.trim();
  return userInstruction ? userInstruction + '\\n\\n' + protocol : protocol;
}
