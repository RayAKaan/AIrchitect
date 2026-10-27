const LOCATION_HINTS = ['Riyadh', 'Jeddah', 'Dammam', 'Bengaluru', 'Dubai', 'Abu Dhabi', 'Doha', 'London'] as const;
const BUILDING_HINTS = ['retail', 'office', 'commercial', 'cafe', 'restaurant', 'villa', 'residential', 'hotel', 'school', 'warehouse', 'mixed-use', 'mixed use'] as const;

export type ProjectOnboardingDraft = { name: string; buildingType: string; location: string; brief: string };

export function normalizeProjectIntent(intent: string): ProjectOnboardingDraft {
  const brief = intent.trim().replace(/\s+/g, ' ');
  const name = (brief.split(/[.!?]/)[0] || 'Untitled architectural project').slice(0, 72);
  const location = LOCATION_HINTS.find((value) => brief.toLowerCase().includes(value.toLowerCase())) || 'Saudi Arabia';
  const hint = BUILDING_HINTS.find((value) => brief.toLowerCase().includes(value));
  const buildingType = hint === 'mixed use' ? 'mixed-use' : hint || 'commercial';
  return { name, buildingType, location, brief };
}

export function onboardingStorageKey(projectId: string): string { return `airchitect:onboarding-intent:${projectId}`; }

export function savePendingOnboarding(projectId: string, brief: string): void {
  sessionStorage.setItem(onboardingStorageKey(projectId), brief);
}

export function takePendingOnboarding(projectId: string): string | null {
  const key = onboardingStorageKey(projectId);
  const brief = sessionStorage.getItem(key);
  if (brief) sessionStorage.removeItem(key);
  return brief;
}
