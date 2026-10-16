import { Module } from '@nestjs/common';
import { WorkflowTemplates } from './workflow.templates';

@Module({
  providers: [WorkflowTemplates],
  exports: [WorkflowTemplates],
})
export class WorkflowsModule {}
