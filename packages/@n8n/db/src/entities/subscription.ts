import { Entity, PrimaryGeneratedColumn, Column, ManyToOne, JoinColumn } from '@n8n/typeorm';

import { WithTimestamps } from './abstract-entity';
import { Project } from './project';

@Entity()
export class Subscription extends WithTimestamps {
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
		type: String,
		default: 'starter',
	})
	plan: string;

	@Column({
		type: Number,
		default: 5,
	})
	maxUsers: number;

	@Column({
		type: Number,
		default: 20,
	})
	maxWorkflows: number;

	@Column({
		type: Number,
		default: 10000,
	})
	maxExecutionsPerMonth: number;

	@Column({
		type: Boolean,
		default: true,
	})
	active: boolean;
}
