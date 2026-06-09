import { Entity, PrimaryGeneratedColumn, Column, ManyToOne, JoinColumn } from '@n8n/typeorm';

import { WithTimestamps } from './abstract-entity';
import { Project } from './project';

@Entity()
export class NodePermission extends WithTimestamps {
	@PrimaryGeneratedColumn('uuid')
	id: string;

	@Column()
	projectId: string;

	@ManyToOne(() => Project, {
		onDelete: 'CASCADE',
	})
	@JoinColumn({ name: 'projectId' })
	project: Project;

	@Column({
		length: 255,
	})
	nodeName: string;

	@Column({
		type: Boolean,
		default: true,
	})
	enabled: boolean;
}
