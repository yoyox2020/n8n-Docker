import { MigrationInterface, QueryRunner, Table } from '@n8n/typeorm';

export class CreateSubscriptionTable1770000000000 implements MigrationInterface {
	public async up(queryRunner: QueryRunner): Promise<void> {
		await queryRunner.createTable(
			new Table({
				name: 'subscription',
				columns: [
					{
						name: 'id',
						type: 'uuid',
						isPrimary: true,
					},
					{
						name: 'projectId',
						type: 'varchar',
					},
					{
						name: 'plan',
						type: 'varchar',
					},
					{
						name: 'maxUsers',
						type: 'int',
					},
					{
						name: 'maxWorkflows',
						type: 'int',
					},
					{
						name: 'maxExecutionsPerMonth',
						type: 'int',
					},
					{
						name: 'active',
						type: 'boolean',
					},
				],
			}),
		);
	}

	public async down(queryRunner: QueryRunner): Promise<void> {
		await queryRunner.dropTable('subscription');
	}
}
