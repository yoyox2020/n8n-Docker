import { DataSource, Repository } from '@n8n/typeorm';
import { Service } from '@n8n/di';

import { Subscription } from '../entities/subscription';

@Service()
export class SubscriptionRepository extends Repository<Subscription> {
	constructor(dataSource: DataSource) {
		super(Subscription, dataSource.manager);
	}

	async findByProject(projectId: string) {
		return await this.findOne({
			where: {
				projectId,
			},
		});
	}
}
