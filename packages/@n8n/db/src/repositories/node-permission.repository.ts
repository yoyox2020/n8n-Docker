import { DataSource, Repository } from '@n8n/typeorm';
import { Service } from '@n8n/di';

import { NodePermission } from '../entities/node-permission';

@Service()
export class NodePermissionRepository extends Repository<NodePermission> {
	constructor(dataSource: DataSource) {
		super(NodePermission, dataSource.manager);
	}

	async getAllowedNodes(projectId: string) {
		return await this.find({
			where: {
				projectId,
				enabled: true,
			},
		});
	}
}
