import { ExecutionsConfig, GlobalConfig } from '@n8n/config';
import type { ModuleInterface } from '@n8n/decorators';
import { BackendModule, OnShutdown } from '@n8n/decorators';
import { Container } from '@n8n/di';
import { InstanceSettings } from 'n8n-core';

@BackendModule({ name: 'chat-hub' })
export class ChatHubModule implements ModuleInterface {
	async init() {
		await import('./chat-hub.controller');
		await import('./chat-hub.settings.controller');
		const { ChatHubEventRelay } = await import('./chat-hub-event-relay.service');
		const { MistikaCredentialProvisionService } = await import(
			'./mistika-credential-provision.service'
		);

		Container.get(ChatHubEventRelay);

		// Auto-provision credential mistikaAiApi dari MISTIKA_* env vars
		// sehingga dashboard external cukup set .env sekali, semua fitur langsung berjalan
		await Container.get(MistikaCredentialProvisionService).provisionFromEnv();

		// In queue mode, only workers process Chat hub execution lifecycle events.
		// Skip initializing the watcher on main instance to avoid unnecessary event subscriptions.
		const isQueueMode = Container.get(ExecutionsConfig).mode === 'queue';
		const isWorker = Container.get(InstanceSettings).isWorker;
		if (!isQueueMode || isWorker) {
			await import('./chat-hub-execution-watcher.service');
		}
	}

	async settings() {
		const { ChatHubSettingsService } = await import('./chat-hub.settings.service');
		const service = Container.get(ChatHubSettingsService);
		const [enabled, providers, semanticSearch] = await Promise.all([
			service.getEnabled(),
			service.getAllProviderSettings(),
			service.getSemanticSearchSettings(),
		]);

		return {
			enabled,
			providers,
			semanticSearch,
			agentUploadMaxSizeMb: Container.get(GlobalConfig).endpoints.formDataFileSizeMax,
		};
	}

	async entities() {
		const { ChatHubSession } = await import('./chat-hub-session.entity');
		const { ChatHubMessage } = await import('./chat-hub-message.entity');
		const { ChatHubAgent } = await import('./chat-hub-agent.entity');
		const { ChatHubTool } = await import('./chat-hub-tool.entity');

		return [ChatHubSession, ChatHubMessage, ChatHubAgent, ChatHubTool];
	}

	@OnShutdown()
	async shutdown() {}
}
