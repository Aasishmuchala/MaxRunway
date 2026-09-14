import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StdioClientTransport} from '@modelcontextprotocol/sdk/client/stdio.js';
import {createReadStream} from 'node:fs';
import {stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
export const ENDPOINT = 'https://mcp.runwayml.com/mcp';

export function unpack(result) {
  if (result.isError) throw new Error('Runway rejected the call: ' + safeText(result));
  if (result.structuredContent) return result.structuredContent;
  for (const item of result.content ?? []) {
    if (item.type === 'text') {
      try { return JSON.parse(item.text); } catch { /* next content block */ }
    }
  }
  throw new Error('Runway returned no structured result. Update the adapter before submitting again.');
}

function safeText(result) {
  return (result.content ?? []).filter(x => x.type === 'text').map(x => x.text).join(' ')
    .replace(/https?:\/\/\S+/g, '[link]').slice(0, 700);
}

export function toolName(tools, wanted) {
  const found = tools.filter(t => t.name === wanted || t.name.endsWith('_' + wanted));
  if (found.length !== 1) throw new Error('Missing or ambiguous Runway MCP tool: ' + wanted);
  return found[0].name;
}

export class RunwayMcp {
  constructor(log = () => {}) { this.log = log; }

  async connect() {
    if (!process.env.LOCALAPPDATA) throw new Error('Windows LOCALAPPDATA is required for the OAuth cache.');
    this.client = new Client({name: 'MaxRunway', version: '0.2.0'}, {capabilities: {}});
    this.transport = new StdioClientTransport({
      command: process.execPath,
      args: [path.join(here, 'node_modules/mcp-remote/dist/proxy.js'), ENDPOINT,
        '--transport', 'http-only', '--auth-timeout', '180'],
      env: {...process.env, MCP_REMOTE_CONFIG_DIR: path.join(process.env.LOCALAPPDATA, 'MaxRunway', 'mcp-auth')},
      stderr: 'pipe',
    });
    // mcp-remote handles browser sign-in; its raw diagnostics may contain tokens.
    this.transport.stderr?.on('data', data => {
      const text = String(data);
      if (/waiting for authorization|waiting for.*callback/i.test(text))
        this.log('Waiting for Runway browser authorization to finish.');
      if (/Auth code received, resolving promise|Authorization completed successfully/i.test(text))
        this.log('Browser authorization received. Completing the connection...');
      if (/Could not open a browser automatically/i.test(text))
        this.log('The browser could not open automatically. Run the connection from an interactive Windows session.');
    });
    this.log('Connecting to Runway. Complete browser sign-in if prompted.');
    await this.client.connect(this.transport, {timeout: 240000});
    this.tools = [];
    let cursor;
    do {
      const page = await this.client.listTools(cursor ? {cursor} : {});
      this.tools.push(...page.tools);
      cursor = page.nextCursor;
    } while (cursor);
    const identity = await this.call('whoami', {rationale: 'Connect the 3ds Max cinematic panel.'});
    if (!identity.authenticated) throw new Error('Runway sign-in was not completed.');
    this.identity = identity;
    return identity;
  }

  async call(name, args) {
    return unpack(await this.client.callTool({name: toolName(this.tools, name), arguments: args},
      undefined, {timeout: 300000}));
  }

  inputSchema(name) {
    const exact = toolName(this.tools, name);
    return this.tools.find(tool => tool.name === exact)?.inputSchema;
  }

  async upload(filename, mimeType) {
    const info = await stat(filename);
    const init = await this.call('init_upload', {
      filename: path.basename(filename), fileSize: info.size, mimeType,
      rationale: 'Upload the exported V-Ray cinematic reference selected in 3ds Max.',
    });
    if (init.kind === 'upload_complete' && init.assetUrl) return init.assetUrl;
    if (!init.uploadId || !init.uploadUrls?.length) throw new Error('Upload initialization did not return upload URLs.');
    const size = init.partSizeBytes ?? info.size;
    if (Math.ceil(info.size / size) !== init.uploadUrls.length) throw new Error('Unexpected multipart upload layout.');
    const parts = [];
    for (let index = 0; index < init.uploadUrls.length; index++) {
      const url = new URL(init.uploadUrls[index]);
      if (url.protocol !== 'https:') throw new Error('Upload requires HTTPS.');
      const start = index * size;
      const end = Math.min(start + size, info.size) - 1;
      const response = await fetch(url, {
        method: 'PUT', headers: {...init.uploadHeaders, 'Content-Type': init.mimeType ?? mimeType,
          'Content-Length': String(end - start + 1)},
        body: createReadStream(filename, {start, end}), duplex: 'half',
        signal: AbortSignal.timeout(600000),
      });
      if (!response.ok) throw new Error('Runway upload failed: HTTP ' + response.status);
      const etag = response.headers.get('etag')?.replace(/^"|"$/g, '');
      if (!etag) throw new Error('Upload returned no ETag; it cannot be finalized.');
      await response.body?.cancel();
      parts.push({partNumber: index + 1, etag});
    }
    const completed = await this.call('complete_upload', {uploadId: init.uploadId, parts});
    if (!completed.assetUrl) throw new Error('Upload did not return a Runway asset URL.');
    return completed.assetUrl;
  }

  async close() { await this.client?.close(); }
}
