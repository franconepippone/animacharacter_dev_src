def display_status_from_json(status: dict) -> str:
    """
    Create a formatted ASCII table from the JSON status dict produced
    by ThreadedLooper.status_as_json().
    
    Args:
        status (dict): Dictionary with keys 'total', 'running', 'paused', 'stopped', 'loops'
    
    Returns:
        str: Multi-line string representing the status table
    """
    WIDTH = 66  # total inner width

    def box_line(content: str = "", sep: str = "║") -> str:
        return f"{sep} {content.ljust(WIDTH - 2)} {sep}"

    def separator(char="═"):
        return f"╠{char * WIDTH}╣"

    def top():
        return f"╔{'═' * WIDTH}╗"

    def bottom():
        return f"╚{'═' * WIDTH}╝"

    lines = ["", top()]
    lines.append(box_line("THREADED LOOPER STATUS"))
    lines.append(separator())

    total = status.get("total", 0)
    running = status.get("running", 0)
    paused = status.get("paused", 0)
    stopped = status.get("stopped", 0)

    lines.append(box_line(f"Total: {total} | Running: {running} | Paused: {paused} | Stopped: {stopped}"))
    lines.append(separator())

    for loop in status.get("loops", []):
        lines.append(box_line(f"Loop ID: {loop.get('id')}, name: {loop.get('name')}"))
        lines.append(box_line(f"  State              : {loop.get('state')}"))
        lines.append(box_line(f"  Frequency          : {loop.get('freq'):.3f} Hz"))
        lines.append(box_line(f"  Thread Alive       : {loop.get('is_running')}"))
        lines.append(box_line(f"  CtxMng Type          : {loop.get('lock_type')}"))
        lines.append(box_line(f"  Exception Callback : {'YES' if loop.get('exception_cb') else 'NO'}"))
        lines.append(separator())

    if lines:
        lines[-1] = bottom()  # replace last separator with bottom border

    return "\n".join(lines)
