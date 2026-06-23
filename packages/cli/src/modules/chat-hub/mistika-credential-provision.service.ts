import { Logger } from '@n8n/backend-common';
import { CredentialsRepository } from '@n8n/db';
import { Service } from '@n8n/di';

import { CredentialsService } from '@/credentials/credentials.service';
import { OwnershipService } from '@/services/ownership.service';

/**
 * Auto-creates or updates the mistikaAiApi credential from MISTIKA_* env vars on startup.
 * Allows external provisioning dashboard to configure LLM in one place (.env),
 * and have it automatically available in n8n without manual credential setup.
 */
@Service()
export class MistikaCredentialProvisionService {
	constructor(
		private readonly logger: Logger,
		private readonly credentialsRepository: CredentialsRepository,
		private readonly credentialsService: CredentialsService,
		private readonly ownershipService: OwnershipService,
	) {}

	async provisionFromEnv(): Promise<void> {
		const apiKey = process.env.MISTIKA_API_KEY;
		const baseUrl = process.env.MISTIKA_BASE_URL;

		if (!apiKey || !baseUrl) {
			return;
		}

		const authHeader = process.env.MISTIKA_AUTH_HEADER ?? 'x-api-key';
		const chatPath = process.env.MISTIKA_CHAT_PATH ?? '/chat/streamchat';
		const defaultModel = process.env.MISTIKA_MODEL ?? '';

		const credentialData = {
			apiKey,
			url: baseUrl,
			authType: authHeader === 'Authorization' ? 'bearer' : 'x-api-key',
			chatPath,
			defaultModel,
			skipSslVerification: false,
		};

		try {
			const existing = await this.credentialsRepository.findOne({
				where: { type: 'mistikaAiApi' },
			});

			if (existing) {
				// Update dengan config terbaru dari env
				const encrypted = await this.credentialsService.createEncryptedData({
					id: existing.id,
					name: existing.name,
					type: existing.type,
					data: credentialData,
				});
				await this.credentialsService.update(existing.id, encrypted, credentialData);
				this.logger.info('[MistikaProvision] Credential mistikaAiApi updated from env vars');
			} else {
				// Buat credential baru untuk instance owner
				const owner = await this.ownershipService.getInstanceOwner();
				await this.credentialsService.createManagedCredential(
					{
						name: 'Mistika-AI account',
						type: 'mistikaAiApi',
						data: credentialData,
					},
					owner,
				);
				this.logger.info('[MistikaProvision] Credential mistikaAiApi created from env vars');
			}
		} catch (error) {
			// Jangan crash startup jika provisioning gagal
			this.logger.warn(
				`[MistikaProvision] Failed to provision credential: ${error instanceof Error ? error.message : String(error)}`,
			);
		}
	}
}
