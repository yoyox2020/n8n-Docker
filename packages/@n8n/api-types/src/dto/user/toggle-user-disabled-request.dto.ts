import { z } from 'zod';

import { Z } from '../../zod-class';

export class ToggleUserDisabledRequestDto extends Z.class({
	disabled: z.boolean(),
}) {}
