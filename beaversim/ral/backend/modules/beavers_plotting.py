"""
beavers_plotting.py

Reusable plotting utilities for Beavers simulation visualization.
"""

from typing import Any, Optional, List, Tuple
import matplotlib.pyplot as plt
from beaversim.ral.backend.modules.module_colors import ColorMaps




def plot_environment_heatmap(
    environment: Any,
    agents: List[Any],
    color_maps: ColorMaps,
    width: int,
    height: int,
    gui: bool = False,
    plot_agents: bool = True
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
    vmax = getattr(environment, '_vegetation_quality_range', [0, 1])[1]
    map_width = first_agent._local_map.shape[0] if getattr(first_agent, '_local_map', None) is not None else width
    map_height = first_agent._local_map.shape[1] if getattr(first_agent, '_local_map', None) is not None else height

    # 3. Create figure and axes
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(25, 8))
    for ax in (ax1, ax2, ax3):
        ax.add_patch(plt.Rectangle((0, 0), map_width, map_height, fill=False, edgecolor='black', linestyle='-', linewidth=2))

    try:
        # 4. Normalize and plot maps
        if getattr(first_agent, '_local_map', None) is not None:
            local_map_init = environment._initial_map[:map_width, :map_height] / vmax
            local_map_norm = environment._map / vmax
            local_map_visits_norm = environment._map_visits_roles / (environment.np.max(environment.np.abs(environment._map_visits_roles) + 1e-5))
            vmin = -environment._streams_depth

            im1 = ax1.imshow(local_map_init.transpose(), origin='lower', cmap=cm._bluebrowngreen_colormap,
                             alpha=cm._whiteblack_colormap_alpha, vmin=vmin/vmax, vmax=1)
            im2 = ax2.imshow(local_map_norm.transpose(), origin='lower', cmap=cm._bluebrowngreen_colormap,
                             alpha=cm._whiteblack_colormap_alpha, vmin=vmin/vmax, vmax=1)
            im3 = ax3.imshow(local_map_visits_norm.transpose(), origin='lower', cmap=cm._visits_colormap, alpha=1, vmin=-1, vmax=1)

            # 5. Overlay negative values (e.g., rivers)
            neg_mask = local_map_norm < 0
            if environment.np.any(neg_mask):
                ax3.imshow(environment.np.where(neg_mask, local_map_norm, environment.np.nan).transpose(), origin='lower',
                           cmap='gray', alpha=0.1, vmin=vmin/vmax, vmax=0)
        else:
            vmin = -environment._streams_depth
            map_norm = environment._map_original / vmax
            im1 = ax1.imshow(map_norm.transpose(), origin='lower', cmap=cm._bluebrowngreen_colormap,
                             alpha=cm._whiteblack_colormap_alpha, vmin=vmin/vmax, vmax=1)
            im2 = ax2.imshow(map_norm.transpose(), origin='lower', cmap=cm._bluebrowngreen_colormap,
                             alpha=cm._whiteblack_colormap_alpha, vmin=vmin/vmax, vmax=1)
            im3 = ax3.imshow(environment.np.zeros_like(map_norm).transpose(), origin='lower', cmap=cm._visits_colormap, alpha=1, vmin=-1, vmax=1)

            neg_mask = map_norm < 0
            if environment.np.any(neg_mask):
                ax3.imshow(environment.np.where(neg_mask, map_norm, environment.np.nan).transpose(), origin='lower',
                           cmap='gray', alpha=0.1, vmin=vmin/vmax, vmax=0)
    except Exception as e:
        print(f"Error during map normalization or plotting: {e}")
        return None

    # 6. Add colorbars
    plt.subplots_adjust(right=0.85)
    cbar1 = plt.colorbar(im2, cax=fig.add_axes([0.86, 0.15, 0.02, 0.7]))
    cbar1.set_label('Vegetation Quality / Elevation', rotation=270, labelpad=20)
    tick_vals = environment.np.linspace(vmin, vmax, 9)
    cbar1.set_ticks(tick_vals / vmax)
    cbar1.set_ticklabels([f'{v:.1f}' for v in tick_vals])
    cbar2 = plt.colorbar(im3, cax=fig.add_axes([0.92, 0.15, 0.02, 0.7]))
    cbar2.set_label('Visit Frequency', rotation=270, labelpad=20)

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

    for agent in agents:
        if hasattr(agent, '_home_base_position_store') and agent._home_base_position_store:
            for hx, hy in agent._home_base_position_store:
                if 0 <= hx < map_width and 0 <= hy < map_height:
                    ax2.add_patch(plt.Rectangle((hx-2, hy-2), 3, 3, fill=True, edgecolor=cm._black, facecolor=cm._gray, linestyle='-', linewidth=2))

    # 8. Configure axes and add time info
    titles = ["Vegetation Quality (Initial)", "Vegetation Quality (Current)", "Visits (Current)"]
    for ax, title in zip((ax1, ax2, ax3), titles):
        ax.set_aspect('equal')
        ax.grid(False)
        ax.set_xlabel('X [pixels]', fontsize=12)
        ax.set_ylabel('Y [pixels]', fontsize=12)
        ax.set_xlim(-0.5, map_width+0.5)
        ax.set_ylim(-0.5, map_height+0.5)
        ax.set_title(title)

    ax3.text(0.5, 1, f"DAY: {getattr(environment, '_current_day', '?')} HOUR: {getattr(environment, '_current_hour', '?')}h",
              fontsize=14, color=cm._black, font='monospace')

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
    1. Organize agents by role (explorer/expander).
    2. Create figure and axes for each agent.
    3. For each agent, plot distance, load, error, and exploration eta.
    4. Add legends, labels, and handle missing data.
    5. Show or return the figure.
    """
    # 1. Organize agents by role
    explorers = [a for a in agents if hasattr(a, '_role') and a._role == 'explorer']
    expanders = [a for a in agents if hasattr(a, '_role') and a._role == 'expander']
    agent_list = (explorers + expanders) if (explorers or expanders) else agents

    if not agent_list:
        print("No agents found for plotting")
        return None

    # 2. Create figure and axes
    n = len(agent_list)
    fig, axes = plt.subplots(n, 4, figsize=(25, 4 * n))
    if n == 1:
        axes = axes.reshape(1, -1)

    # 3. Process each agent
    for i, agent in enumerate(agent_list):
        role = getattr(agent, '_role', 'unknown')
        positions, loads, errors, etas = agent._position_store, agent._load_store, agent._error_store, agent._exploration_eta_store

        if positions:
            init_pos = positions[0]
            time_steps = list(range(len(positions)))
            distances, river_times, river_dists = [], [], []
            for t, pos in enumerate(positions):
                dist = environment.np.sqrt((pos[0] - init_pos[0])**2 + (pos[1] - init_pos[1])**2)
                distances.append(dist)
                if hasattr(environment, '_map') and environment._map is not None:
                    x, y = int(pos[0]), int(pos[1])
                    if 0 <= x < environment._map.shape[0] and 0 <= y < environment._map.shape[1]:
                        if environment._map[x, y] < -2:
                            river_times.append(t)
                            river_dists.append(dist)
            # Distance plot
            axes[i, 0].plot(time_steps, distances, color='black', linewidth=2, alpha=0.8)
            if river_times:
                axes[i, 0].scatter(river_times, river_dists, color='blue', marker='o', s=50, alpha=0.8,
                                 edgecolors='darkblue', linewidth=1, label='In River')
                axes[i, 0].legend()
            axes[i, 0].axhline(y=0, color='gray', linestyle='--', alpha=0.5)
            axes[i, 0].set_xlabel('Time Steps')
            axes[i, 0].set_ylabel('Distance from Start')
            axes[i, 0].set_title(f'Agent {agent.unique_id}: Distance from Initial Position')
            axes[i, 0].grid(True, alpha=0.3)
            axes[i, 0].text(0.95, 0.95, f'Role: {role.capitalize()}', transform=axes[i, 0].transAxes, fontsize=10,
                          va='top', ha='right', bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgray', alpha=0.8, edgecolor='black'))
            # Load plot
            axes[i, 1].plot(time_steps, loads, color='black', linewidth=2, alpha=0.8, label='Current Load')
            if hasattr(agent, '_maximum_load_store') and agent._maximum_load_store:
                axes[i, 1].plot(time_steps[:len(agent._maximum_load_store)], agent._maximum_load_store,
                              color='red', linewidth=1.5, alpha=0.7, linestyle='--', label='Maximum Load Capacity')
            axes[i, 1].set_xlabel('Time Steps')
            axes[i, 1].set_ylabel('Load Amount')
            axes[i, 1].set_title(f'Agent {agent.unique_id}: Load Variation')
            axes[i, 1].grid(True, alpha=0.3)
            axes[i, 1].set_ylim(0, getattr(agent, '_maximum_load_init', 1) + 1)
            axes[i, 1].legend()
            # Error plot
            error_norms = [environment.np.linalg.norm(e) if hasattr(e, '__len__') and len(e) > 0 else abs(e) if e is not None else 0.0 for e in errors]
            if error_norms:
                axes[i, 2].plot(time_steps[:len(error_norms)], error_norms, color='black', linewidth=2, alpha=0.8)
                axes[i, 2].set_xlabel('Time Steps')
                axes[i, 2].set_ylabel('Error Norm')
                axes[i, 2].set_title(f'Agent {agent.unique_id}: Control Error Norm')
                axes[i, 2].grid(True, alpha=0.3)
            else:
                axes[i, 2].text(0.5, 0.5, 'No error data available', ha='center', va='center', transform=axes[i, 2].transAxes)
                axes[i, 2].set_title(f'Agent {agent.unique_id}: Control Error Norm')
            # Exploration eta plot
            if etas:
                axes[i, 3].plot(time_steps[:len(etas)], etas, color='black', linewidth=2, alpha=0.8, label='Exploration Eta')
                if hasattr(agent, '_harvest_threshold_store') and agent._harvest_threshold_store:
                    lower = [th[0] for th in agent._harvest_threshold_store if len(th) >= 2]
                    upper = [th[1] for th in agent._harvest_threshold_store if len(th) >= 2]
                    if lower and upper:
                        axes[i, 3].plot(time_steps[:len(lower)], lower, color='red', linewidth=1.5, alpha=0.7, linestyle='--', label='Harvest Threshold Min')
                        axes[i, 3].plot(time_steps[:len(upper)], upper, color='orange', linewidth=1.5, alpha=0.7, linestyle='--', label='Harvest Threshold Max')
                axes[i, 3].set_xlabel('Time Steps')
                axes[i, 3].set_ylabel('Values')
                axes[i, 3].set_title(f'Agent {agent.unique_id}: Exploration Eta & Harvest Thresholds')
                axes[i, 3].grid(True, alpha=0.3)
                axes[i, 3].legend()
                axes[i, 3].set_ylim(0, getattr(agent, '_vegetation_quality_range', [0, 1])[1] + 0.5)
            else:
                axes[i, 3].text(0.5, 0.5, 'No exploration eta data available', ha='center', va='center', transform=axes[i, 3].transAxes)
                axes[i, 3].set_title(f'Agent {agent.unique_id}: Exploration Eta & Harvest Thresholds')
        else:
            for j, title in enumerate([
                f'Agent {agent.unique_id}: Distance from Initial Position',
                f'Agent {agent.unique_id}: Load Variation',
                f'Agent {agent.unique_id}: Control Error Norm',
                f'Agent {agent.unique_id}: Exploration Eta & Harvest Thresholds']):
                axes[i, j].text(0.5, 0.5, 'No data available', ha='center', va='center', transform=axes[i, j].transAxes)
                axes[i, j].set_title(title)
            axes[i, 0].text(0.95, 0.95, f'Role: {role.capitalize()}', transform=axes[i, 0].transAxes, fontsize=10,
                          va='top', ha='right', bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgray', alpha=0.8, edgecolor='black'))

    # 4. Finalize layout and show/return
    plt.tight_layout()
    if gui:
        plt.show()
    return fig
