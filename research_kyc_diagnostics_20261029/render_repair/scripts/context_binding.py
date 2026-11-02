"""One local semantic change at MjRenderContext.render's already-locked entry."""
def bind_in_existing_render_lock(renderer, lock, record):
    assert lock.locked(), 'must be called inside original MjSim.render lock'
    renderer.gl_ctx.make_current()
    state=record('repair_after_single_make_current',renderer.gl_ctx)
    if not state['match']:raise RuntimeError('binding failed; no repeated binding')
    return state
