import Router from '@koa/router'
import {
  createFileProvider,
  resolvePrometheusPath,
  isSensitivePath,
  MAX_EDIT_SIZE,
} from '../../services/prometheus/file-provider'

export const fileRoutes = new Router()

function handleError(ctx: any, err: any) {
  const code = err.code || 'unknown'
  const statusMap: Record<string, number> = {
    missing_path: 400,
    invalid_path: 400,
    not_found: 404,
    ENOENT: 404,
    already_exists: 409,
    permission_denied: 403,
    file_too_large: 413,
    not_a_directory: 400,
    not_a_file: 400,
    unsupported_backend: 501,
    backend_error: 502,
    backend_timeout: 504,
  }
  ctx.status = statusMap[code] || 500
  ctx.body = { error: err.message, code }
}

// GET /api/prometheus/files/list?path=
fileRoutes.get('/api/prometheus/files/list', async (ctx) => {
  const relativePath = (ctx.query.path as string) || ''
  try {
    const absPath = resolvePrometheusPath(relativePath)
    const provider = await createFileProvider()
    const entries = await provider.listDir(absPath)
    entries.sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1
      return a.name.localeCompare(b.name)
    })
    ctx.body = { entries, path: relativePath }
  } catch (err: any) {
    handleError(ctx, err)
  }
})

// GET /api/prometheus/files/stat?path=
fileRoutes.get('/api/prometheus/files/stat', async (ctx) => {
  const relativePath = ctx.query.path as string
  if (!relativePath) {
    ctx.status = 400
    ctx.body = { error: 'Missing path parameter', code: 'missing_path' }
    return
  }
  try {
    const absPath = resolvePrometheusPath(relativePath)
    const provider = await createFileProvider()
    const info = await provider.stat(absPath)
    ctx.body = info
  } catch (err: any) {
    handleError(ctx, err)
  }
})

// GET /api/prometheus/files/read?path=
fileRoutes.get('/api/prometheus/files/read', async (ctx) => {
  const relativePath = ctx.query.path as string
  if (!relativePath) {
    ctx.status = 400
    ctx.body = { error: 'Missing path parameter', code: 'missing_path' }
    return
  }
  try {
    const absPath = resolvePrometheusPath(relativePath)
    const provider = await createFileProvider()
    const data = await provider.readFile(absPath)
    if (data.length > MAX_EDIT_SIZE) {
      ctx.status = 413
      ctx.body = { error: 'File too large to edit', code: 'file_too_large' }
      return
    }
    ctx.body = { content: data.toString('utf-8'), path: relativePath, size: data.length }
  } catch (err: any) {
    handleError(ctx, err)
  }
})

// PUT /api/prometheus/files/write  body: { path, content }
fileRoutes.put('/api/prometheus/files/write', async (ctx) => {
  const { path: relativePath, content } = ctx.request.body as { path?: string; content?: string }
  if (!relativePath) {
    ctx.status = 400
    ctx.body = { error: 'Missing path parameter', code: 'missing_path' }
    return
  }
  if (isSensitivePath(relativePath)) {
    ctx.status = 403
    ctx.body = { error: 'Cannot modify sensitive file', code: 'permission_denied' }
    return
  }
  try {
    const buf = Buffer.from(content || '', 'utf-8')
    if (buf.length > MAX_EDIT_SIZE) {
      ctx.status = 413
      ctx.body = { error: 'Content too large', code: 'file_too_large' }
      return
    }
    const absPath = resolvePrometheusPath(relativePath)
    const provider = await createFileProvider()
    await provider.writeFile(absPath, buf)
    ctx.body = { ok: true, path: relativePath }
  } catch (err: any) {
    handleError(ctx, err)
  }
})

// DELETE /api/prometheus/files/delete  body: { path, recursive? }
fileRoutes.delete('/api/prometheus/files/delete', async (ctx) => {
  const { path: relativePath, recursive } = ctx.request.body as { path?: string; recursive?: boolean }
  if (!relativePath) {
    ctx.status = 400
    ctx.body = { error: 'Missing path parameter', code: 'missing_path' }
    return
  }
  if (isSensitivePath(relativePath)) {
    ctx.status = 403
    ctx.body = { error: 'Cannot delete sensitive file', code: 'permission_denied' }
    return
  }
  try {
    const absPath = resolvePrometheusPath(relativePath)
    const provider = await createFileProvider()
    if (recursive) {
      await provider.deleteDir(absPath)
    } else {
      await provider.deleteFile(absPath)
    }
    ctx.body = { ok: true }
  } catch (err: any) {
    handleError(ctx, err)
  }
})

// POST /api/prometheus/files/rename  body: { oldPath, newPath }
fileRoutes.post('/api/prometheus/files/rename', async (ctx) => {
  const { oldPath, newPath } = ctx.request.body as { oldPath?: string; newPath?: string }
  if (!oldPath || !newPath) {
    ctx.status = 400
    ctx.body = { error: 'Missing oldPath or newPath', code: 'missing_path' }
    return
  }
  if (isSensitivePath(oldPath)) {
    ctx.status = 403
    ctx.body = { error: 'Cannot rename sensitive file', code: 'permission_denied' }
    return
  }
  try {
    const absOld = resolvePrometheusPath(oldPath)
    const absNew = resolvePrometheusPath(newPath)
    const provider = await createFileProvider()
    await provider.renameFile(absOld, absNew)
    ctx.body = { ok: true }
  } catch (err: any) {
    handleError(ctx, err)
  }
})

// POST /api/prometheus/files/mkdir  body: { path }
fileRoutes.post('/api/prometheus/files/mkdir', async (ctx) => {
  const { path: relativePath } = ctx.request.body as { path?: string }
  if (!relativePath) {
    ctx.status = 400
    ctx.body = { error: 'Missing path parameter', code: 'missing_path' }
    return
  }
  try {
    const absPath = resolvePrometheusPath(relativePath)
    const provider = await createFileProvider()
    await provider.mkDir(absPath)
    ctx.body = { ok: true }
  } catch (err: any) {
    handleError(ctx, err)
  }
})

// POST /api/prometheus/files/copy  body: { srcPath, destPath }
fileRoutes.post('/api/prometheus/files/copy', async (ctx) => {
  const { srcPath, destPath } = ctx.request.body as { srcPath?: string; destPath?: string }
  if (!srcPath || !destPath) {
    ctx.status = 400
    ctx.body = { error: 'Missing srcPath or destPath', code: 'missing_path' }
    return
  }
  try {
    const absSrc = resolvePrometheusPath(srcPath)
    const absDest = resolvePrometheusPath(destPath)
    const provider = await createFileProvider()
    await provider.copyFile(absSrc, absDest)
    ctx.body = { ok: true }
  } catch (err: any) {
    handleError(ctx, err)
  }
})

// POST /api/prometheus/files/upload?path=  (multipart/form-data)
fileRoutes.post('/api/prometheus/files/upload', async (ctx) => {
  const targetDir = (ctx.query.path as string) || ''
  const contentType = ctx.get('content-type') || ''
  if (!contentType.startsWith('multipart/form-data')) {
    ctx.status = 400
    ctx.body = { error: 'Expected multipart/form-data', code: 'invalid_request' }
    return
  }

  const boundary = '--' + contentType.split('boundary=')[1]
  if (!boundary || boundary === '--undefined') {
    ctx.status = 400
    ctx.body = { error: 'Missing boundary', code: 'invalid_request' }
    return
  }

  const chunks: Buffer[] = []
  for await (const chunk of ctx.req) chunks.push(chunk)
  const raw = Buffer.concat(chunks)

  const boundaryBuf = Buffer.from(boundary)
  const parts = splitMultipart(raw, boundaryBuf)
  const provider = await createFileProvider()
  const results: { name: string; path: string }[] = []

  for (const part of parts) {
    const headerEnd = part.indexOf(Buffer.from('\r\n\r\n'))
    if (headerEnd === -1) continue
    const headerBuf = part.subarray(0, headerEnd)
    const header = headerBuf.toString('utf-8')
    const data = part.subarray(headerEnd + 4, part.length - 2)

    let filename = ''
    const filenameStarMatch = header.match(/filename\*=UTF-8''(.+)/i)
    if (filenameStarMatch) {
      filename = decodeURIComponent(filenameStarMatch[1])
    } else {
      const filenameMatch = header.match(/filename="([^"]+)"/)
      if (!filenameMatch) continue
      filename = filenameMatch[1]
    }

    if (data.length > MAX_EDIT_SIZE) {
      ctx.status = 413
      ctx.body = { error: `File ${filename} too large`, code: 'file_too_large' }
      return
    }

    const filePath = targetDir ? `${targetDir}/${filename}` : filename
    if (isSensitivePath(filePath)) {
      ctx.status = 403
      ctx.body = { error: `Cannot overwrite sensitive file: ${filename}`, code: 'permission_denied' }
      return
    }

    const absPath = resolvePrometheusPath(filePath)
    await provider.writeFile(absPath, data)
    results.push({ name: filename, path: filePath })
  }

  ctx.body = { files: results }
})

function splitMultipart(raw: Buffer, boundary: Buffer): Buffer[] {
  const parts: Buffer[] = []
  let start = 0
  while (true) {
    const idx = raw.indexOf(boundary, start)
    if (idx === -1) break
    if (start > 0) {
      const partStart = start + 2
      parts.push(raw.subarray(partStart, idx))
    }
    start = idx + boundary.length
  }
  return parts
}
