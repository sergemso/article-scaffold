// Minimal JSON Schema validator (zero dependencies) for the keywords our schemas use:
// type, enum, const, required, properties, additionalProperties, items, pattern,
// minimum, maximum, minItems, patternProperties. Returns a list of "path: message" errors.

const typeOf = (v) => (v === null ? 'null' : Array.isArray(v) ? 'array' : Number.isInteger(v) ? 'integer' : typeof v);

function matchesType(value, type) {
  const actual = typeOf(value);
  const types = Array.isArray(type) ? type : [type];
  return types.some((t) => t === actual || (t === 'number' && actual === 'integer'));
}

export function validate(schema, value, path = '$', rootSchema = schema) {
  if (schema.$ref) {
    const m = /^#\/\$defs\/(.+)$/.exec(schema.$ref);
    if (!m || !rootSchema.$defs?.[m[1]]) throw new Error(`unsupported $ref ${schema.$ref}`);
    return validate(rootSchema.$defs[m[1]], value, path, rootSchema);
  }
  const errors = [];
  if (schema.type && !matchesType(value, schema.type)) {
    return [`${path}: expected ${[].concat(schema.type).join('|')}, got ${typeOf(value)}`];
  }
  if (schema.const !== undefined && value !== schema.const) errors.push(`${path}: must equal ${JSON.stringify(schema.const)}`);
  if (schema.enum && !schema.enum.includes(value)) errors.push(`${path}: must be one of ${schema.enum.join(', ')}`);
  if (typeof value === 'string' && schema.pattern && !new RegExp(schema.pattern).test(value)) {
    errors.push(`${path}: must match ${schema.pattern}`);
  }
  if (typeof value === 'number') {
    if (schema.minimum !== undefined && value < schema.minimum) errors.push(`${path}: must be >= ${schema.minimum}`);
    if (schema.maximum !== undefined && value > schema.maximum) errors.push(`${path}: must be <= ${schema.maximum}`);
  }
  if (Array.isArray(value)) {
    if (schema.minItems !== undefined && value.length < schema.minItems) errors.push(`${path}: needs >= ${schema.minItems} items`);
    if (schema.items) value.forEach((item, i) => errors.push(...validate(schema.items, item, `${path}[${i}]`, rootSchema)));
  }
  if (typeOf(value) === 'object') {
    for (const key of schema.required ?? []) if (!(key in value)) errors.push(`${path}: missing required "${key}"`);
    for (const [key, v] of Object.entries(value)) {
      const sub =
        schema.properties?.[key] ??
        Object.entries(schema.patternProperties ?? {}).find(([re]) => new RegExp(re).test(key))?.[1];
      if (sub) errors.push(...validate(sub, v, `${path}.${key}`, rootSchema));
      else if (schema.additionalProperties === false) errors.push(`${path}: unknown property "${key}"`);
      else if (typeof schema.additionalProperties === 'object') errors.push(...validate(schema.additionalProperties, v, `${path}.${key}`, rootSchema));
    }
  }
  return errors;
}
