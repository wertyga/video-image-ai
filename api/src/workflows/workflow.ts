export type NodeRef = [string, number];
export type Workflow = Record<string, { class_type: string; inputs: Record<string, unknown>; _meta?: object }>;

export interface LoraRef {
  name: string;
  strength: number;
}

/** Подключает LoRA цепочкой после `model` (узлы 30, 31, ...) и возвращает выход последней. */
export function chainLoras(workflow: Workflow, model: NodeRef, loras: LoraRef[]): NodeRef {
  loras.forEach(({ name, strength }, i) => {
    const id = String(30 + i);
    workflow[id] = {
      class_type: 'LoraLoaderModelOnly',
      inputs: { model, lora_name: name, strength_model: strength },
    };
    model = [id, 0];
  });
  return model;
}

/** Переименовывает узлы с префиксом, чтобы два workflow можно было слить в один граф. */
export function prefixNodes(workflow: Workflow, prefix: string): Workflow {
  const isRef = (value: unknown): value is NodeRef =>
    Array.isArray(value) && value.length === 2 && typeof value[0] === 'string' && value[0] in workflow;
  return Object.fromEntries(
    Object.entries(workflow).map(([id, node]) => [
      prefix + id,
      {
        ...node,
        inputs: Object.fromEntries(
          Object.entries(node.inputs).map(([key, value]) => [key, isRef(value) ? [prefix + value[0], value[1]] : value]),
        ),
      },
    ]),
  );
}

/** {character} в промпте заменяется ссылкой на персонажа; без метки ссылка (если нужна) идёт в начало. */
export const CHARACTER_TAG = '{character}';

export function insertCharacter(prompt: string, ref: string, prependIfMissing = true): string {
  if (prompt.includes(CHARACTER_TAG)) return prompt.replaceAll(CHARACTER_TAG, ref);
  return prependIfMissing ? `${ref}, ${prompt}` : prompt;
}

/** nsfw — реалистично с NSFW LoRA; anime — рисованный стиль (NSFW LoRA остаётся, её силу задаёт lora). */
export const MODES = ['nsfw', 'anime'] as const;
export type Mode = (typeof MODES)[number];
