"""
beavers_plotting.py

Reusable plotting utilities for Beavers simulation visualization.
"""

from typing import Any, Optional, List, Tuple
import numpy as np
import matplotlib.pyplot as plt
import re
from pathlib import Path
from beaversim.ral.backend.modules.module_colors import ColorMaps


TITLE_FONT_SIZE = 20
LABEL_FONT_SIZE = 20
TICK_FONT_SIZE = 20
LEGEND_FONT_SIZE = 20
ANNOTATION_FONT_SIZE = 20
COLORBAR_LABEL_FONT_SIZE = 20
COLORBAR_TICK_FONT_SIZE = 20
SHOW_PLOT_TITLES = False

# Heatmap-specific style constants (keep centralized for readability tuning)
HEATMAP_FIGSIZE = (30, 10)
HEATMAP_FRAME_LINE_WIDTH = 2
HEATMAP_VISIT_MARKER_LINE_WIDTH = 0.8
HEATMAP_VISIT_MARKER_SIZE_DEFAULT = 32.0
HEATMAP_DESTINATION_MARKER_SIZE = 200.0
HEATMAP_TRAJECTORY_LINE_WIDTH = 2.0
HEATMAP_TRAJECTORY_ALPHA = 0.8
HEATMAP_HOME_RECT_OFFSET = 2
HEATMAP_HOME_RECT_SIZE = 3
HEATMAP_HOME_RECT_LINE_WIDTH = 2
HEATMAP_HOME_VISITS_CIRCLE_SIZE = 140
HEATMAP_HOME_VISITS_CIRCLE_LINE_WIDTH = 3.0
HEATMAP_TIME_ANNOTATION_FONT_SIZE = ANNOTATION_FONT_SIZE + 2

# Simulation recap style constants
RECAP_FIG_WIDTH = 30
RECAP_FIG_HEIGHT_PER_AGENT = 5
RECAP_MAIN_LINE_WIDTH = 2.5
RECAP_AUX_LINE_WIDTH = 1.8
RECAP_RIVER_MARKER_SIZE = 70
RECAP_RIVER_MARKER_LINE_WIDTH = 1.2
RECAP_GRID_ALPHA = 0.35
RECAP_ROLE_BOX_ALPHA = 0.85

# Motion diagnostics style constants
DIAGNOSTICS_FIG_WIDTH_PER_AGENT = 14
DIAGNOSTICS_FIG_HEIGHT = 10
DIAGNOSTICS_FIG_HEIGHT_PER_PANEL = 4.5
DIAGNOSTICS_MAIN_LINE_WIDTH = 2.8
DIAGNOSTICS_AUX_LINE_WIDTH = 2.0
DIAGNOSTICS_MARKER_SIZE = 110
DIAGNOSTICS_MARKER_LINE_WIDTH = 2.4
DIAGNOSTICS_GRID_ALPHA = 0.35
DIAGNOSTICS_HPAD = 3.2


def _get_resolution_m(environment: Any) -> float:
    resolution_m = getattr(environment, '_resolution_m', None)
    try:
        resolution_m = float(resolution_m)
    except (TypeError, ValueError):
        resolution_m = 1.0
    return resolution_m if resolution_m > 0 else 1.0


def _get_timedelta_hours(environment: Any) -> float:
    timedelta_hours = getattr(environment, '_timedelta', None)
    try:
        timedelta_hours = float(timedelta_hours)
    except (TypeError, ValueError):
        timedelta_hours = 1.0
    return timedelta_hours if timedelta_hours > 0 else 1.0


def _set_meter_ticks(ax: Any, width_px: float, height_px: float, resolution_m: float) -> None:
    x_ticks_px = np.linspace(0, width_px, num=6)
    y_ticks_px = np.linspace(0, height_px, num=6)

    ax.set_xticks(x_ticks_px)
    ax.set_yticks(y_ticks_px)
    ax.set_xticklabels([f'{tick * resolution_m:.1f}' for tick in x_ticks_px])
    ax.set_yticklabels([f'{tick * resolution_m:.1f}' for tick in y_ticks_px])


def _style_axis(ax: Any, title: str, xlabel: str, ylabel: str) -> None:
    if SHOW_PLOT_TITLES:
        ax.set_title(title, fontsize=TITLE_FONT_SIZE)
    else:
        ax.set_title('')
    ax.set_xlabel(xlabel, fontsize=LABEL_FONT_SIZE)
    ax.set_ylabel(ylabel, fontsize=LABEL_FONT_SIZE)
    ax.tick_params(axis='both', labelsize=TICK_FONT_SIZE)


def _place_horizontal_legend(ax: Any, fontsize: int = LEGEND_FONT_SIZE, ncol: int = 3) -> None:
    handles, labels = ax.get_legend_handles_labels()
    if not handles:
        return
    ax.legend(
        handles,
        labels,
        loc='upper center',
        bbox_to_anchor=(0.5, -0.25),
        ncol=ncol,
        frameon=True,
        fontsize=fontsize,
        borderaxespad=0.0,
        columnspacing=1.2,
        handletextpad=0.6,
    )


def _get_visualizer_agents(backend: Any) -> List[Any]:
    agents: List[Any] = []

    schedule = getattr(backend, '_schedule', None)
    if schedule is not None and hasattr(schedule, 'agents'):
        agents = list(schedule.agents)

    if not agents and schedule is not None and hasattr(schedule, '_agents'):
        raw_schedule_agents = schedule._agents
        if isinstance(raw_schedule_agents, dict):
            agents = list(raw_schedule_agents.values())
        else:
            agents = list(raw_schedule_agents)

    if not agents and hasattr(backend, '_agents'):
        raw_backend_agents = backend._agents
        if isinstance(raw_backend_agents, dict):
            agents = list(raw_backend_agents.values())
        else:
            agents = list(raw_backend_agents)

    return agents


def _destination_changed(prev_dest: Any, curr_dest: Any) -> bool:
    if prev_dest is None and curr_dest is None:
        return False
    if (prev_dest is None) != (curr_dest is None):
        return True

    prev_arr = np.asarray(prev_dest)
    curr_arr = np.asarray(curr_dest)

    if prev_arr.shape != curr_arr.shape:
        return True

    try:
        return not np.allclose(prev_arr.astype(float), curr_arr.astype(float), atol=1e-9)
    except (TypeError, ValueError):
        return not np.array_equal(prev_arr, curr_arr)


def _extract_snapshot_index(filename: str) -> Optional[int]:
    match = re.search(r'_(\d+)\.npy$', filename)
    return int(match.group(1)) if match else None


def _boost_signed_contrast(values: Any, gamma: float = 0.05) -> Any:
    values_arr = np.asarray(values, dtype=float)
    boosted = np.sign(values_arr) * np.power(np.abs(values_arr), gamma)
    return np.clip(boosted, -1.0, 1.0)


def _get_visit_marker_points(
    local_map_visits_norm: Any,
    threshold: float,
) -> Tuple[Any, Any]:
    marker_mask = np.abs(local_map_visits_norm) > threshold
    marker_points = np.argwhere(marker_mask)
    if marker_points.size == 0:
        return marker_points, np.asarray([])

    marker_values = local_map_visits_norm[marker_mask]
    return marker_points, marker_values

def plot_environment_heatmap(
    environment: Any,
    agents: List[Any],
    color_maps: ColorMaps,
    width: int,
    height: int,
    gui: bool = False,
    plot_agents: bool = True,
    plot_visit_markers: bool = False,
    plot_agent_trajectories: bool = False,
    plot_motion_destination: bool = False,
    visit_marker_threshold: float = 0.0,
    visit_marker_size: float = HEATMAP_VISIT_MARKER_SIZE_DEFAULT,
    destination_marker_size: float = HEATMAP_DESTINATION_MARKER_SIZE,
) -> Optional[plt.Figure]:
    """
    Plot environment heatmap with agent positions, home bases, and time info.

    Args:
        environment: The environment object containing map and state.
        agents: List of agent objects (must have _local_map, _position, _role, etc.).
        color_maps: ColorMaps instance for colormap settings.
        width: Width of the map.
        height: Height of the map.
        gui: If True, show the plot interactively.
        plot_agents: If True, plot agent positions and home bases.
        plot_visit_markers: If True, overlay circular markers on visited pixels.
        plot_agent_trajectories: If True, plot full agent trajectories on the visits axis.
        plot_motion_destination: If True, plot the motion destination of each agent.
        visit_marker_threshold: Minimum absolute normalized visit value to mark.
        visit_marker_size: Size of the visit markers in points^2.
        destination_marker_size: Size of the destination markers in points^2.
    Returns:
        The matplotlib Figure object, or None if plotting fails.

    Steps:
    1. Get first agent for map reference.
    2. Extract map parameters and create figure/axes.
    3. Normalize and plot maps (initial, current, visits).
    4. Overlay negative values (e.g., rivers).
    5. Add colorbars for vegetation and visits.
    6. Plot agent positions and home bases if requested.
    7. Configure axes and add time info.
    8. Show or return the figure.
    """
    # 1. Get first agent for map reference
    first_agent = next((a for a in agents if hasattr(a, '_local_map')), None)
    if not first_agent:
        print("No agents found for local map visualization")
        return None

    # 2. Extract map parameters
    is_day = getattr(environment, '_time_of_day', 'day') == 'day'
    cm = color_maps
    vegetation_vmin = -environment._streams_depth
    vegetation_vmax = environment._vegetation_quality_range[1]
    resolution_m = _get_resolution_m(environment)
    map_width = first_agent._local_map.shape[0] if getattr(first_agent, '_local_map', None) is not None else width
    map_height = first_agent._local_map.shape[1] if getattr(first_agent, '_local_map', None) is not None else height

    # 3. Create figure and axes
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=HEATMAP_FIGSIZE)
    for ax in (ax1, ax2, ax3):
        ax.add_patch(
            plt.Rectangle(
                (0, 0),
                map_width,
                map_height,
                fill=False,
                edgecolor='black',
                linestyle='-',
                linewidth=HEATMAP_FRAME_LINE_WIDTH,
            )
        )
        
    # visits
    visits_scale = float(environment.np.max(environment.np.abs(environment._map_visits_roles)))
    if visits_scale <= 0:
        visits_scale = 1.0
    local_map_visits_norm = environment.np.clip(environment._map_visits_roles / visits_scale, -1.0, 1.0)
    local_map_visits_display = _boost_signed_contrast(local_map_visits_norm)

    try:
        # 4. Normalize and plot maps
        if getattr(first_agent, '_local_map', None) is not None:
            local_map_init = environment._initial_map[:map_width, :map_height]
            local_map_norm = environment._map

            im1 = ax1.imshow(local_map_init.transpose(), origin='lower', cmap=cm._bluebrowngreen_colormap,
                             alpha=cm._whiteblack_colormap_alpha, vmin=vegetation_vmin, vmax=vegetation_vmax)
            im2 = ax2.imshow(local_map_norm.transpose(), origin='lower', cmap=cm._bluebrowngreen_colormap,
                             alpha=cm._whiteblack_colormap_alpha, vmin=vegetation_vmin, vmax=vegetation_vmax)
            im3 = ax3.imshow(local_map_visits_display.transpose(), origin='lower', cmap=cm._visits_colormap, alpha=1, vmin=-1, vmax=1)

            if plot_visit_markers:
                marker_points, marker_values = _get_visit_marker_points(local_map_visits_display, visit_marker_threshold)
                if marker_points.size > 0:
                    ax3.scatter(
                        marker_points[:, 0],
                        marker_points[:, 1],
                        c=marker_values,
                        cmap=cm._visits_colormap,
                        vmin=-1,
                        vmax=1,
                        s=visit_marker_size,
                        marker='o',
                        edgecolors='face',
                        linewidths=HEATMAP_VISIT_MARKER_LINE_WIDTH,
                        alpha=0.95,
                    )                    

            # 5. Overlay negative values (e.g., rivers)
            neg_mask = local_map_norm < 0
            if environment.np.any(neg_mask):
                ax3.imshow(environment.np.where(neg_mask, local_map_norm, environment.np.nan).transpose(), origin='lower',
                           cmap='gray', alpha=0.05, vmin=vegetation_vmin/vegetation_vmax, vmax=0)
        else:
            map_norm = environment._map_original
            im1 = ax1.imshow(map_norm.transpose(), origin='lower', cmap=cm._bluebrowngreen_colormap,
                             alpha=cm._whiteblack_colormap_alpha, vmin=vegetation_vmin, vmax=vegetation_vmax)
            im2 = ax2.imshow(map_norm.transpose(), origin='lower', cmap=cm._bluebrowngreen_colormap,
                             alpha=cm._whiteblack_colormap_alpha, vmin=vegetation_vmin, vmax=vegetation_vmax)
            im3 = ax3.imshow(local_map_visits_display.transpose(), origin='lower', cmap=cm._visits_colormap, alpha=1, vmin=-1, vmax=1)

            if plot_visit_markers:
                marker_points, marker_values = _get_visit_marker_points(local_map_visits_display, visit_marker_threshold)
                if marker_points.size > 0:
                    ax3.scatter(
                        marker_points[:, 0],
                        marker_points[:, 1],
                        c=marker_values,
                        cmap=cm._visits_colormap,
                        vmin=-1,
                        vmax=1,
                        s=visit_marker_size,
                        marker='o',
                        edgecolors='face',
                        linewidths=HEATMAP_VISIT_MARKER_LINE_WIDTH,
                        alpha=0.95,
                    )
            
            neg_mask = map_norm < 0
            if environment.np.any(neg_mask):
                ax3.imshow(environment.np.where(neg_mask, map_norm, environment.np.nan).transpose(), origin='lower',
                           cmap='gray', alpha=0.05, vmin=vegetation_vmin, vmax=0)
    except Exception as e:
        print(f"Error during map normalization or plotting: {e}")
        return None

    # 6. Add colorbars
    plt.subplots_adjust(right=0.85)
    cbar1 = plt.colorbar(im2, cax=fig.add_axes([0.86, 0.15, 0.02, 0.7]))
    cbar1.set_label('Vegetation Quality / Elevation', rotation=270, labelpad=24, fontsize=COLORBAR_LABEL_FONT_SIZE)
    tick_vals = environment.np.linspace(vegetation_vmin, vegetation_vmax, 9)
    cbar1.set_ticks(tick_vals)
    cbar1.set_ticklabels([f'{v:.1f}' for v in tick_vals])
    cbar1.ax.tick_params(labelsize=COLORBAR_TICK_FONT_SIZE)
    cbar2 = plt.colorbar(im3, cax=fig.add_axes([0.92, 0.15, 0.02, 0.7]))
    cbar2.set_label('Visit Frequency', rotation=270, labelpad=24, fontsize=COLORBAR_LABEL_FONT_SIZE)
    cbar2.set_ticks([-1, 0, 1])
    cbar2.set_ticklabels(['Explorers', 'Neutral', 'Builders'])
    cbar2.ax.tick_params(labelsize=COLORBAR_TICK_FONT_SIZE)

    # 7. Plot agents and home bases
    if plot_agents:
        if is_day:
            marker, msize, medge, mwidth, malpha = cm._agent_marker, cm._agent_markersize_small, cm._agent_markeredgecolor, cm._agent_markeredgewidth, cm._agent_markeralpha
        else:
            marker, msize, medge, mwidth, malpha = cm._agent_marker_night, cm._agent_markersize_small_night, cm._agent_markeredgecolor_night, cm._agent_markeredgewidth_night, cm._agent_markeralpha_night

        for agent in agents:
            if hasattr(agent, '_position') and hasattr(agent, '_role'):
                x, y = agent._position
                if 0 <= x < map_width and 0 <= y < map_height:
                    color = 'red' if agent._role == 'explorer' else 'black'
                    ax2.plot(x, y, marker, markersize=msize, markeredgecolor=medge, markerfacecolor=color, markeredgewidth=mwidth, alpha=malpha)

    if plot_agent_trajectories:
        for agent in agents:
            position_store = getattr(agent, '_position_store', None)
            if not position_store:
                continue

            trajectory = np.asarray(position_store, dtype=float)
            if trajectory.ndim != 2 or trajectory.shape[1] < 2:
                continue

            valid_x = (trajectory[:, 0] >= 0) & (trajectory[:, 0] < map_width)
            valid_y = (trajectory[:, 1] >= 0) & (trajectory[:, 1] < map_height)
            valid_mask = valid_x & valid_y
            if not np.any(valid_mask):
                continue

            trajectory = trajectory[valid_mask]
            if trajectory.shape[0] < 2:
                continue

            role = getattr(agent, '_role', 'unknown')
            line_color = 'red' if role == 'explorer' else 'cyano'
            ax2.plot(
                trajectory[:, 0],
                trajectory[:, 1],
                color=line_color,
                linewidth=HEATMAP_TRAJECTORY_LINE_WIDTH,
                alpha=HEATMAP_TRAJECTORY_ALPHA,
            )
            ax3.plot(
                trajectory[:, 0],
                trajectory[:, 1],
                color=line_color,
                linewidth=HEATMAP_TRAJECTORY_LINE_WIDTH,
                alpha=HEATMAP_TRAJECTORY_ALPHA,
            )

    motion_destination: Optional[Tuple[float, float]] = None
    for agent in agents:
        dest = getattr(agent, '_motion_destination', None)
        if dest is None:
            continue
        try:
            dx, dy = float(dest[0]), float(dest[1])
        except (TypeError, ValueError, IndexError):
            continue
        if 0 <= dx < map_width and 0 <= dy < map_height:
            motion_destination = (dx, dy)
            break

    for agent in agents:
        if hasattr(agent, '_home_base_position_store') and agent._home_base_position_store:
            for hx, hy in agent._home_base_position_store:
                if 0 <= hx < map_width and 0 <= hy < map_height:                    
                    ax2.scatter(
                        hx,
                        hy,
                        s=HEATMAP_HOME_VISITS_CIRCLE_SIZE,
                        marker='o',
                        facecolors='limegreen',
                        edgecolors='forestgreen',
                        linewidths=HEATMAP_HOME_VISITS_CIRCLE_LINE_WIDTH,
                        alpha=0.9,
                        zorder=6,
                    )
                    ax3.scatter(
                        hx,
                        hy,
                        s=HEATMAP_HOME_VISITS_CIRCLE_SIZE,
                        marker='o',
                        facecolors='limegreen',
                        edgecolors='forestgreen',
                        linewidths=HEATMAP_HOME_VISITS_CIRCLE_LINE_WIDTH,
                        alpha=0.9,
                        zorder=6,
                    )

    if motion_destination is not None and plot_motion_destination == True:
        ax2.scatter(
            motion_destination[0],
            motion_destination[1],
            s=destination_marker_size,
            marker='o',
            color='magenta',
            edgecolors='darkmagenta',
            linewidths=HEATMAP_VISIT_MARKER_LINE_WIDTH,
            alpha=0.95,
            label='Motion Destination',
        )
        ax3.scatter(
            motion_destination[0],
            motion_destination[1],
            s=destination_marker_size,
            marker='o',
            color='magenta',
            edgecolors='darkmagenta',
            linewidths=HEATMAP_VISIT_MARKER_LINE_WIDTH,
            alpha=0.95,
            label='Motion Destination',
        )

    # 8. Configure axes and add time info
    titles = ["Vegetation Quality (Initial)", "Vegetation Quality (Current)", "Visits (Current)"]
    for ax, title in zip((ax1, ax2, ax3), titles):
        ax.set_aspect('equal')
        ax.grid(False)
        ax.set_xlim(-0.5, map_width+0.5)
        ax.set_ylim(-0.5, map_height+0.5)
        _set_meter_ticks(ax, map_width, map_height, resolution_m)
        _style_axis(ax, title, 'X [m]', 'Y [m]')

    # ax3.text(0.5, 1, f"DAY: {int(getattr(environment, '_current_day', '?'))} HOUR: {int(getattr(environment, '_current_hour', '?'))}",
    #           fontsize=HEATMAP_TIME_ANNOTATION_FONT_SIZE, color=cm._black, font='monospace')

    # 9. Show or return the figure
    if gui:
        plt.show()
    return fig

def plot_simulation_recap(
    agents: List[Any],
    environment: Any,
    gui: bool = False
) -> Optional[plt.Figure]:
    """
    Plot N×4 subplots: distance, load, error norm, and exploration eta for each agent.

    Args:
        agents: List of agent objects (must have _position_store, _load_store, etc.).
        environment: The environment object (must have .np and _map).
        gui: If True, show the plot interactively.

    Returns:
        The matplotlib Figure object, or None if plotting fails.

    Steps:
    1. Organize agents by role (explorer/builder).
    2. Create figure and axes for each agent.
    3. For each agent, plot distance, load, error, and exploration eta.
    4. Add legends, labels, and handle missing data.
    5. Show or return the figure.
    """
    # 1. Organize agents by role
    explorers = [a for a in agents if hasattr(a, '_role') and a._role == 'explorer']
    builders = [a for a in agents if hasattr(a, '_role') and a._role == 'builder']
    agent_list = (explorers + builders) if (explorers or builders) else agents

    if not agent_list:
        print("No agents found for plotting")
        return None

    resolution_m = _get_resolution_m(environment)
    timedelta_hours = _get_timedelta_hours(environment)
    timestep_days = timedelta_hours / 24.0

    # 2. Create figure and axes
    n = len(agent_list)
    fig, axes = plt.subplots(n, 4, figsize=(RECAP_FIG_WIDTH, RECAP_FIG_HEIGHT_PER_AGENT * n))
    if n == 1:
        axes = axes.reshape(1, -1)

    # 3. Process each agent
    for i, agent in enumerate(agent_list):
        role = getattr(agent, '_role', 'unknown')
        positions, loads, errors, etas = agent._position_store, agent._load_store, agent._error_store, agent._exploration_eta_store

        if positions:
            init_pos = positions[0]
            time_days = np.arange(len(positions)) * timestep_days
            distances, river_times, river_dists = [], [], []
            for t, pos in enumerate(positions):
                dist = environment.np.sqrt((pos[0] - init_pos[0])**2 + (pos[1] - init_pos[1])**2) * resolution_m
                distances.append(dist)
                if hasattr(environment, '_map') and environment._map is not None:
                    x, y = int(pos[0]), int(pos[1])
                    if 0 <= x < environment._map.shape[0] and 0 <= y < environment._map.shape[1]:
                        if environment._map[x, y] < -2:
                            river_times.append(t * timestep_days)
                            river_dists.append(dist)
            # Distance plot
            axes[i, 0].plot(time_days, distances, color='black', linewidth=RECAP_MAIN_LINE_WIDTH, alpha=0.85)
            if river_times:
                axes[i, 0].scatter(river_times, river_dists, color='blue', marker='o', s=RECAP_RIVER_MARKER_SIZE, alpha=0.85,
                                 edgecolors='darkblue', linewidth=RECAP_RIVER_MARKER_LINE_WIDTH, label='In River')
                axes[i, 0].legend(fontsize=LEGEND_FONT_SIZE)
            axes[i, 0].axhline(y=0, color='gray', linestyle='--', alpha=0.5)
            _style_axis(axes[i, 0], f'Agent {agent.unique_id}: Distance from Initial Position', 'Time [days]', 'Distance from Start [m]')
            axes[i, 0].grid(True, alpha=RECAP_GRID_ALPHA)
            axes[i, 0].text(0.95, 0.95, f'Role: {role.capitalize()}', transform=axes[i, 0].transAxes, fontsize=ANNOTATION_FONT_SIZE,
                          va='top', ha='right', bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgray', alpha=RECAP_ROLE_BOX_ALPHA, edgecolor='black'))
            # Load plot
            axes[i, 1].plot(time_days, loads, color='black', linewidth=RECAP_MAIN_LINE_WIDTH, alpha=0.85, label='Current Load')
            if hasattr(agent, '_maximum_load_store') and agent._maximum_load_store:
                axes[i, 1].plot(time_days[:len(agent._maximum_load_store)], agent._maximum_load_store,
                              color='red', linewidth=RECAP_AUX_LINE_WIDTH, alpha=0.75, linestyle='--', label='Maximum Load Capacity')
            _style_axis(axes[i, 1], f'Agent {agent.unique_id}: Load Variation', 'Time [days]', 'Load Amount')
            axes[i, 1].grid(True, alpha=RECAP_GRID_ALPHA)
            axes[i, 1].set_ylim(0, getattr(agent, '_maximum_load_init', 1) + 1)
            axes[i, 1].legend(fontsize=LEGEND_FONT_SIZE)
            # Error plot
            error_norms = [environment.np.linalg.norm(e) if hasattr(e, '__len__') and len(e) > 0 else abs(e) if e is not None else 0.0 for e in errors]
            if error_norms:
                axes[i, 2].plot(time_days[:len(error_norms)], error_norms, color='black', linewidth=RECAP_MAIN_LINE_WIDTH, alpha=0.85)
                _style_axis(axes[i, 2], f'Agent {agent.unique_id}: Control Error Norm', 'Time [days]', 'Error Norm')
                axes[i, 2].grid(True, alpha=RECAP_GRID_ALPHA)
            else:
                axes[i, 2].text(0.5, 0.5, 'No error data available', ha='center', va='center', transform=axes[i, 2].transAxes)
                _style_axis(axes[i, 2], f'Agent {agent.unique_id}: Control Error Norm', 'Time [days]', 'Error Norm')
            # Exploration eta plot
            if etas:
                axes[i, 3].plot(time_days[:len(etas)], etas, color='black', linewidth=RECAP_MAIN_LINE_WIDTH, alpha=0.85, label='Exploration Eta')
                if hasattr(agent, '_harvest_threshold_store') and agent._harvest_threshold_store:
                    lower = [th[0] for th in agent._harvest_threshold_store if len(th) >= 2]
                    upper = [th[1] for th in agent._harvest_threshold_store if len(th) >= 2]
                    if lower and upper:
                        axes[i, 3].plot(time_days[:len(lower)], lower, color='red', linewidth=RECAP_AUX_LINE_WIDTH, alpha=0.75, linestyle='--', label='Harvest Threshold Min')
                        axes[i, 3].plot(time_days[:len(upper)], upper, color='orange', linewidth=RECAP_AUX_LINE_WIDTH, alpha=0.75, linestyle='--', label='Harvest Threshold Max')
                _style_axis(axes[i, 3], f'Agent {agent.unique_id}: Exploration Eta & Harvest Thresholds', 'Time [days]', 'Values')
                axes[i, 3].grid(True, alpha=RECAP_GRID_ALPHA)
                axes[i, 3].legend(fontsize=LEGEND_FONT_SIZE)
                axes[i, 3].set_ylim(0, getattr(agent, '_exploration_eta', 1) + 0.5)
            else:
                axes[i, 3].text(0.5, 0.5, 'No exploration eta data available', ha='center', va='center', transform=axes[i, 3].transAxes)
                _style_axis(axes[i, 3], f'Agent {agent.unique_id}: Exploration Eta & Harvest Thresholds', 'Time [days]', 'Values')
        else:
            for j, title in enumerate([
                f'Agent {agent.unique_id}: Distance from Initial Position',
                f'Agent {agent.unique_id}: Load Variation',
                f'Agent {agent.unique_id}: Control Error Norm',
                f'Agent {agent.unique_id}: Exploration Eta & Harvest Thresholds']):
                axes[i, j].text(0.5, 0.5, 'No data available', ha='center', va='center', transform=axes[i, j].transAxes)
                _style_axis(axes[i, j], title, 'Time [days]', 'Values')
            axes[i, 0].text(0.95, 0.95, f'Role: {role.capitalize()}', transform=axes[i, 0].transAxes, fontsize=ANNOTATION_FONT_SIZE,
                          va='top', ha='right', bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgray', alpha=RECAP_ROLE_BOX_ALPHA, edgecolor='black'))

    # 4. Finalize layout and show/return
    plt.tight_layout()
    if gui:
        plt.show()
    return fig


def plot_agent_motion_diagnostics(
    backend: Any,
    accuracy_m: Optional[float] = None,
) -> None:
    """Plot error norm, destination changes, and speed for each agent in the backend.

    The x-axis is expressed in days using the backend/environment timestep.
    """
    environment = getattr(backend, '_environment', None)
    if environment is None:
        print('No environment found for plotting')
        return None

    resolution_m = _get_resolution_m(environment)
    timestep_days = _get_timedelta_hours(environment) / 24.0
    agents = _get_visualizer_agents(backend)

    if not agents:
        print('No agents found for plotting')
        return None

    n = len(agents)
    total_panels = 2 * n
    fig, axes = plt.subplots(
        total_panels,
        1,
        figsize=(DIAGNOSTICS_FIG_WIDTH_PER_AGENT, DIAGNOSTICS_FIG_HEIGHT_PER_PANEL * total_panels),
        squeeze=False,
    )

    for i, agent in enumerate(agents):
        errors = getattr(agent, '_error_store', [])
        positions = getattr(agent, '_position_store', [])
        destinations = getattr(agent, '_destination_store', [])

        error_norms = [
            (np.linalg.norm(e) if hasattr(e, '__len__') and len(e) > 0 else abs(e) if e is not None else 0.0) * resolution_m
            for e in errors
        ]

        speed_values = []
        if len(positions) >= 2:
            position_array = np.asarray(positions, dtype=float)
            step_distances_m = np.linalg.norm(np.diff(position_array, axis=0), axis=1) * resolution_m
            speed_values = step_distances_m / _get_timedelta_hours(environment)

        destination_change_indices: List[int] = []
        if len(destinations) >= 2:
            for step_idx in range(1, len(destinations)):
                if _destination_changed(destinations[step_idx - 1], destinations[step_idx]):
                    destination_change_indices.append(step_idx)

        error_ax = axes[2 * i, 0]
        speed_ax = axes[2 * i + 1, 0]

        if error_norms:
            time_days_error = np.arange(len(error_norms)) * timestep_days
            error_ax.plot(time_days_error, error_norms, color='black', linewidth=DIAGNOSTICS_MAIN_LINE_WIDTH, alpha=0.92, label='Error Norm')

            marker_indices = [idx for idx in destination_change_indices if idx < len(error_norms)]
            if marker_indices:
                marker_times = np.asarray(marker_indices) * timestep_days
                marker_vals = [error_norms[idx] for idx in marker_indices]
                error_ax.scatter(
                    marker_times,
                    marker_vals,
                    s=DIAGNOSTICS_MARKER_SIZE,
                    facecolors='none',
                    edgecolors='tab:orange',
                    linewidths=DIAGNOSTICS_MARKER_LINE_WIDTH,
                    label='Destination changed',
                )

            if accuracy_m is not None:
                error_ax.axhline(
                    accuracy_m,
                    color='red',
                    linestyle='--',
                    linewidth=DIAGNOSTICS_AUX_LINE_WIDTH,
                    alpha=0.9,
                    label=f'Accuracy threshold: {accuracy_m:.2f} m',
                )

            _style_axis(error_ax, f'Agent {agent.unique_id}: Control Error Norm', 'Time [days]', 'Error Norm [m]')
            error_ax.grid(True, alpha=DIAGNOSTICS_GRID_ALPHA)
            error_ax.set_xlim(0, time_days_error[-1] if len(time_days_error) > 0 else 1)
            _place_horizontal_legend(error_ax, fontsize=LEGEND_FONT_SIZE, ncol=3)
        else:
            error_ax.text(0.5, 0.5, 'No error data available', ha='center', va='center', transform=error_ax.transAxes)
            if accuracy_m is not None:
                error_ax.axhline(
                    accuracy_m,
                    color='red',
                    linestyle='--',
                    linewidth=DIAGNOSTICS_AUX_LINE_WIDTH,
                    alpha=0.9,
                    label=f'Accuracy threshold: {accuracy_m:.2f} m',
                )
                _place_horizontal_legend(error_ax, fontsize=LEGEND_FONT_SIZE, ncol=3)
            _style_axis(error_ax, f'Agent {agent.unique_id}: Control Error Norm', 'Time [days]', 'Error Norm [m]')

        if len(speed_values) > 0:
            time_days_speed = np.arange(1, len(positions)) * timestep_days
            average_speed = float(np.mean(speed_values))
            speed_ax.plot(time_days_speed, speed_values, color='tab:blue', linewidth=DIAGNOSTICS_MAIN_LINE_WIDTH, alpha=0.92, label='Speed')
            speed_ax.axhline(average_speed, color='tab:red', linestyle='--', linewidth=DIAGNOSTICS_AUX_LINE_WIDTH, alpha=0.85, label=f'Average: {average_speed:.2f} m/h')
            _style_axis(speed_ax, f'Agent {agent.unique_id}: Speed', 'Time [days]', 'Speed [m/h]')
            speed_ax.grid(True, alpha=DIAGNOSTICS_GRID_ALPHA)
            speed_ax.set_xlim(0, time_days_speed[-1] if len(time_days_speed) > 0 else 1)
            _place_horizontal_legend(speed_ax, fontsize=LEGEND_FONT_SIZE, ncol=2)
        else:
            speed_ax.text(0.5, 0.5, 'No speed data available', ha='center', va='center', transform=speed_ax.transAxes)
            _style_axis(speed_ax, f'Agent {agent.unique_id}: Speed', 'Time [days]', 'Speed [m/h]')

    plt.tight_layout(rect=[0.0, 0.03, 1.0, 1.0], h_pad=DIAGNOSTICS_HPAD)
    plt.show()
    plt.close(fig)
    return None


def plot_growth_statistics(backend: Any) -> None:
    """Plot vegetation and growth statistics with a timestep-aware day axis."""
    environment = getattr(backend, '_environment', None)
    if environment is None:
        print('No environment found for plotting')
        return None

    stats = getattr(environment, '_growth_stats', None)
    if not isinstance(stats, dict):
        print('Growth statistics are not available')
        return None

    veg_mean = stats.get('veg_mean', [])
    if len(veg_mean) == 0:
        print('No growth statistics found to plot')
        return None

    timestep_days = _get_timedelta_hours(environment) / 24.0
    time_days = np.arange(len(veg_mean)) * timestep_days

    fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, figsize=(12, 8), sharex=True)

    veg_mean_arr = np.asarray(veg_mean, dtype=float)
    veg_quantiles = np.asarray(stats.get('veg_quantiles', []), dtype=float)
    if veg_quantiles.ndim == 2 and veg_quantiles.shape[1] >= 3 and len(veg_quantiles) == len(veg_mean_arr):
        q25 = veg_quantiles[:, 0]
        q50 = veg_quantiles[:, 1]
        q75 = veg_quantiles[:, 2]
        ax1.plot(time_days, q50, label='Vegetation Median', color='green')
        ax1.plot(time_days, veg_mean_arr, label='Vegetation Mean', color='darkgreen', linestyle='--')
        ax1.fill_between(time_days, q25, q75, color='green', alpha=0.2, label='Q10-Q90')
    else:
        veg_std = np.asarray(stats.get('veg_std', []), dtype=float)
        ax1.plot(time_days, veg_mean_arr, label='Vegetation Mean', color='green')
        if len(veg_std) == len(veg_mean_arr):
            lower = np.maximum(0.0, veg_mean_arr - veg_std)
            upper = veg_mean_arr + veg_std
            ax1.fill_between(time_days, lower, upper, color='green', alpha=0.2, label='Mean ± Std (clipped)')

    _style_axis(ax1, 'Macroscopic Vegetation State Over Time', '', 'Vegetation Value')
    ax1.legend(loc='upper right', fontsize=LEGEND_FONT_SIZE)
    ax1.grid(True)

    growth_mean = np.asarray(stats.get('growth_factor_mean', []), dtype=float)
    growth_std = np.asarray(stats.get('growth_factor_std', []), dtype=float)
    random_mean = np.asarray(stats.get('random_growth_mean', []), dtype=float)
    random_std = np.asarray(stats.get('random_growth_std', []), dtype=float)

    growth_time = time_days[:len(growth_mean)]
    random_time = time_days[:len(random_mean)]

    if len(growth_mean) > 0:
        ax2.plot(growth_time, growth_mean, label='Effective Growth Mean', color='blue', linestyle='--')
        if len(growth_std) == len(growth_mean):
            ax2.fill_between(growth_time, growth_mean - growth_std, growth_mean + growth_std, color='blue', alpha=0.2)

    if len(random_mean) > 0:
        ax2.plot(random_time, random_mean, label='Stochastic Component', color='orange', linestyle='--')
        if len(random_std) == len(random_mean):
            ax2.fill_between(random_time, random_mean - random_std, random_mean + random_std, color='orange', alpha=0.2)

    _style_axis(ax2, 'Seasonal Drive and Stochastic Growth Factors', 'Simulation Time [days]', 'Growth Rate ($\Delta v$)')
    ax2.legend(loc='upper right', fontsize=LEGEND_FONT_SIZE)
    ax2.grid(True)

    plt.tight_layout()
    plt.show()
    plt.close(fig)
    return None


def plot_two_vegetation_npy_with_backend_grid(
    backend: Any,
    real_npy_path: Any,
    sim_npy_path: Any,
    show_colorbar: bool = False,
) -> Optional[plt.Figure]:
    """Compare two vegetation .npy matrices side-by-side using backend grid conventions."""
    environment = getattr(backend, '_environment', None)
    if environment is None:
        print('No environment found for plotting')
        return None

    reference_map = getattr(environment, '_map', None)
    if reference_map is None:
        reference_map = getattr(environment, '_initial_map', None)
    if reference_map is None:
        print('No reference map found in environment for plotting')
        return None

    grid_w, grid_h = reference_map.shape[0], reference_map.shape[1]
    resolution_m = _get_resolution_m(environment)

    real_path = Path(real_npy_path)
    sim_path = Path(sim_npy_path)
    if not real_path.exists():
        print(f'Real-data npy not found: {real_path}')
        return None
    if not sim_path.exists():
        print(f'Simulation npy not found: {sim_path}')
        return None

    real_matrix = np.load(str(real_path))
    sim_matrix = np.load(str(sim_path))

    def _align_to_backend_grid(arr: Any, label: str) -> Any:
        if arr.shape == (grid_w, grid_h):
            return arr
        if arr.shape == (grid_h, grid_w):
            print(f'{label}: transposing from {arr.shape} to {(grid_w, grid_h)}')
            return arr.transpose()
        print(f'{label}: shape {arr.shape} does not match backend grid {(grid_w, grid_h)}; plotting as-is')
        return arr

    real_matrix = _align_to_backend_grid(real_matrix, 'Real matrix')
    sim_matrix = _align_to_backend_grid(sim_matrix, 'Simulation matrix')

    cmap_vegetation = ColorMaps()._bluebrowngreen_colormap
    vmin_sim = float(np.min(sim_matrix))
    vmax_sim = float(np.max(sim_matrix))
    vmin_real = float(np.min(real_matrix))
    vmax_real = float(np.max(real_matrix))    

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharex=True, sharey=True)

    # Match the main backend plotting convention (imshow on transposed matrices).
    axes[0].imshow(real_matrix.transpose(), origin='lower', cmap=cmap_vegetation, vmin=vmin_real, vmax=vmax_real)
    axes[1].imshow(sim_matrix.transpose(), origin='lower', cmap=cmap_vegetation, vmin=vmin_sim, vmax=vmax_sim)

    _style_axis(axes[0], 'Real Data', 'X [m]', 'Y [m]')
    _style_axis(axes[1], 'Simulation Snapshot', 'X [m]', 'Y [m]')

    for ax in axes:
        arr_h, arr_w = ax.images[0].get_array().shape
        ax.set_xlim(-0.5, arr_w - 0.5)
        ax.set_ylim(-0.5, arr_h - 0.5)
        _set_meter_ticks(ax, arr_w - 1, arr_h - 1, resolution_m)

    if show_colorbar:
        cbar = fig.colorbar(axes[1].images[0], ax=axes, fraction=0.046, pad=0.04)
        cbar.set_label('Vegetation / Elevation', fontsize=COLORBAR_LABEL_FONT_SIZE)
        cbar.ax.tick_params(labelsize=COLORBAR_TICK_FONT_SIZE)

    plt.tight_layout()
    plt.show()
    plt.close(fig)
    return fig


def plot_spatial_snapshots_by_number(
    backend: Any,
    snapshot_dir: str,
    snapshot_numbers: List[int],
    one_indexed: bool = True,
    show_colorbar: bool = False,
    show_titles: bool = True,   
) -> None:
    """Plot selected snapshots using ordinal numbers from a folder.

    Args:
        backend: Simulation backend with environment and simulation settings.
        snapshot_dir: Folder containing .npy snapshots.
        snapshot_numbers: Ordinal snapshot numbers to load from sorted .npy files.
        one_indexed: If True, snapshot_numbers are 1-based; otherwise 0-based.
        show_colorbar: If True, display colorbar on the plot.
        colormap: The colormap to use for the plot.
        show_titles: If True, display titles with snapshot numbers and day values.
    """
    environment = getattr(backend, '_environment', None)
    if environment is None:
        print('No environment found for plotting')
        return None
    
    snapshot_dir = Path(snapshot_dir)
    dir_maps = snapshot_dir / 'maps'
    dir_visits = snapshot_dir / 'visits'

    # Load maps
    npy_files_maps = sorted(dir_maps.glob('*.npy')) if dir_maps.exists() else []
    if not npy_files_maps:
        print(f'No .npy snapshots found in {dir_maps}')
        return None

    # Load visits
    npy_files_visits = sorted(dir_visits.glob('*.npy')) if dir_visits.exists() else []

    selected_info: List[Tuple[int, Path, Path, int]] = []
    for num in snapshot_numbers:
        file_idx = (num - 1) if one_indexed else num
        if file_idx < 0 or file_idx >= len(npy_files_maps):
            print(f'Snapshot number {num} is out of range (available: 1 to {len(npy_files_maps)} when one_indexed=True)')
            continue

        map_path = npy_files_maps[file_idx]
        visits_path = npy_files_visits[file_idx] if file_idx < len(npy_files_visits) else None
        
        parsed_idx = _extract_snapshot_index(map_path.name)
        snapshot_idx = parsed_idx if parsed_idx is not None else file_idx
        selected_info.append((num, map_path, visits_path, snapshot_idx))

    if not selected_info:
        print('No valid snapshot numbers selected')
        return None

    maps = [np.load(str(info[1])) for info in selected_info]
    visits = [np.load(str(info[2])) if info[2] is not None else None for info in selected_info]
    
    cmap_instance = ColorMaps()
    cmap_vegetation = cmap_instance._bluebrowngreen_colormap
    cmap_visits = cmap_instance._visits_colormap

    n = len(maps)
    fig, axes = plt.subplots(2, n, figsize=(max(1, n) * 6, 11), sharey='row')
    if n == 1:
        axes = axes.reshape(2, 1)

    vmin_veg = min(m.min() for m in maps)
    vmax_veg = max(m.max() for m in maps)

    # Compute visits normalization across all visits
    vmin_visits = -1.0
    vmax_visits = 1.0
    if any(v is not None for v in visits):
        visits_scale = max(
            float(np.max(np.abs(v))) if v is not None else 0.0 
            for v in visits
        )
        if visits_scale <= 0:
            visits_scale = 1.0
    else:
        visits_scale = 1.0

    resolution_m = _get_resolution_m(environment)
    timedelta_hours = _get_timedelta_hours(environment)
    downsampling = getattr(backend, '_kwargs', {}).get('simulation', {}).get('downsampling', 1)

    for i, (m, v, info) in enumerate(zip(maps, visits, selected_info)):
        selected_num, _, _, snapshot_idx = info
        day_value = (snapshot_idx * downsampling) + 1
        
        # --- Row 0: Vegetation ---
        ax_veg = axes[0, i]
        im_veg = ax_veg.imshow(m, origin='lower', cmap=cmap_vegetation, vmin=vmin_veg, vmax=vmax_veg)
        
        if show_titles:
            ax_veg.set_title(f'Snapshot {selected_num} (Day {day_value:.0f})', fontsize=TITLE_FONT_SIZE)
        else:
            ax_veg.set_title('')
        ax_veg.set_xlabel('X [m]', fontsize=LABEL_FONT_SIZE)
        ax_veg.tick_params(axis='both', labelsize=TICK_FONT_SIZE)
        if i == 0:
            ax_veg.set_ylabel('Y [m]', fontsize=LABEL_FONT_SIZE)
        _set_meter_ticks(ax_veg, m.shape[1] - 1, m.shape[0] - 1, resolution_m)
        
        # --- Row 1: Visits with styling from plot_environment_heatmap ---
        ax_vis = axes[1, i]
        
        if v is not None:
            # Normalize visits
            local_map_visits_norm = np.clip(v / visits_scale, -1.0, 1.0)
            # Boost signed contrast
            local_map_visits_display = _boost_signed_contrast(local_map_visits_norm)
            
            # Plot visits with colormap
            im_vis = ax_vis.imshow(local_map_visits_display, origin='lower', cmap=cmap_visits, vmin=-1, vmax=1)
            
            # Overlay negative vegetation/elevation values (rivers/streams) with semi-transparent gray
            neg_mask = m < 0
            if np.any(neg_mask):
                ax_vis.imshow(np.where(neg_mask, m, np.nan), origin='lower',
                             cmap='gray', alpha=0.05, vmin=vmin_veg, vmax=0)
        else:
            # No visits data
            ax_vis.text(0.5, 0.5, 'No visits data', ha='center', va='center', 
                       transform=ax_vis.transAxes, fontsize=LABEL_FONT_SIZE)
            im_vis = None
        
        ax_vis.set_title('')
        ax_vis.set_xlabel('X [m]', fontsize=LABEL_FONT_SIZE)
        ax_vis.tick_params(axis='both', labelsize=TICK_FONT_SIZE)
        if i == 0:
            ax_vis.set_ylabel('Y [m]', fontsize=LABEL_FONT_SIZE)
        _set_meter_ticks(ax_vis, v.shape[1] - 1 if v is not None else m.shape[1] - 1, 
                        v.shape[0] - 1 if v is not None else m.shape[0] - 1, resolution_m)

    if show_colorbar:
        cbar1 = fig.colorbar(im_veg, ax=axes[0, :], fraction=0.046, pad=0.04, shrink=0.9)
        cbar1.set_label('Vegetation/Elevation', fontsize=COLORBAR_LABEL_FONT_SIZE)
        cbar1.ax.tick_params(labelsize=COLORBAR_TICK_FONT_SIZE)
        
        if im_vis is not None:
            cbar2 = fig.colorbar(im_vis, ax=axes[1, :], fraction=0.046, pad=0.04, shrink=0.9)
            cbar2.set_label('Visit Frequency', fontsize=COLORBAR_LABEL_FONT_SIZE)
            cbar2.set_ticks([-1, 0, 1])
            cbar2.set_ticklabels(['Explorers', 'Neutral', 'Builders'])
            cbar2.ax.tick_params(labelsize=COLORBAR_TICK_FONT_SIZE)

    plt.tight_layout()
    plt.show()
    plt.close(fig)
    return None
