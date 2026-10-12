import { installPayload } from './studymate.mjs';

export const inject = ['agentPresets'];

export async function apply(ctx) {
  const profile = ctx.get?.('profileContext');
  if (!profile || !ctx.agentPresets?.register) {
    console.warn('StudyMate：当前 DSH 不支持原生插件接口（需要 0.1.7-alpha.1+）；已跳过原生加载。旧版请使用 npx -y @yunmiao/studymate@latest install。');
    return;
  }
  try {
    const { registration } = installPayload({
      native: true, profile: profile.name, dshHome: profile.home,
    });
    await ctx.effect(() => ctx.agentPresets.register(registration.config));
  } catch (error) {
    // Startup may report a problem, but must not migrate profile ownership.
    console.warn(`StudyMate：已跳过原生加载。${error instanceof Error ? error.message : String(error)}`);
  }
}
