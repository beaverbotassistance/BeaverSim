import os
import glob
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.collections import LineCollection
from mpl_toolkits.axes_grid1 import make_axes_locatable
from IPython.display import display, HTML
from beaversim.ral.backend.modules.module_colors import ColorMaps

# ============================================================================
# LOAD ALL SIMULATION SNAPSHOTS
# ============================================================================
save_path = 'output/rumney_marsh_rgb_a2'
file_name_pattern = 'environment_map_boston_rumney_marsh_rgb_a2'
file_pattern = os.path.join(save_path, f"{file_name_pattern}_*.npy")
file_paths = sorted(glob.glob(file_pattern), key=_snapshot_index)

if not file_paths:
    print(f"No files found matching pattern: {file_pattern}")
else:
    print(f"Found {len(file_paths)} matrices. Processing all...")
    
# =========================================================================
# PARAMETERS FOR GRAPH CONSTRUCTION
# =========================================================================
base_val = 0.1
sigma = 0.1
delta_D = 2.0
delta_V = 0.5
degree_threshold = 4
lower_bound = base_val - sigma
upper_bound = base_val + sigma
min_value = np.max([0.0, base_val - 3*sigma])  # Minimum value for color normalization
max_value = np.min([1.0, base_val + 3*sigma])  # Maximum value for color normalization

# Read once for stable global scales
loaded_raw = [np.load(fp) for fp in file_paths]
matrix_min = min(mat.min() for mat in loaded_raw)
matrix_max = max(mat.max() for mat in loaded_raw)

frames_data = []
image_h, image_w = None, None

# =========================================================================
# PROCESS EACH MATRIX (BUILD GRAPH DATA)
# =========================================================================
for file_idx, raw_matrix in enumerate(loaded_raw):
    final_matrix = np.flipud(raw_matrix)
    H, W = final_matrix.shape

    if image_h is None:
        image_h, image_w = H, W

    valid_mask = (final_matrix >= lower_bound) & (final_matrix <= upper_bound)
    valid_indices = np.argwhere(valid_mask)

    if len(valid_indices) < 2:
        print(f"  File {file_idx}: Too few nodes ({len(valid_indices)}), skipping")
        continue

    G = nx.Graph()
    node_mapping = {}
    for node_id, (row, col) in enumerate(valid_indices):
        value = final_matrix[row, col]
        G.add_node(node_id, pos=(col, image_h - 1 - row), value=value)
        node_mapping[(row, col)] = node_id

    for i, (row1, col1) in enumerate(valid_indices):
        node1 = node_mapping[(row1, col1)]
        val1 = final_matrix[row1, col1]

        for row2, col2 in valid_indices[i + 1:]:
            dist_sq = (row2 - row1) ** 2 + (col2 - col1) ** 2
            if dist_sq > delta_D**2:
                continue

            distance = np.sqrt(dist_sq)
            val2 = final_matrix[row2, col2]
            value_diff = abs(val1 - val2)

            if distance <= delta_D and value_diff <= delta_V:
                
                # edge value combining distance and value difference
                d_norm = distance / max(delta_D, 1e-12)
                v_norm = value_diff / max(delta_V, 1e-12)

                w_d = 0.5
                w_v = 0.5
                dvalue = w_d * d_norm + w_v * v_norm
                
                node2 = node_mapping[(row2, col2)]
                G.add_edge(node1, node2, distance=distance, value_diff=value_diff, dvalue=dvalue)

    # Remove nodes with degree below threshold after graph construction
    nodes_to_remove = [n for n, deg in G.degree() if deg < degree_threshold]
    if nodes_to_remove:
        G.remove_nodes_from(nodes_to_remove)

    # Build arrays used for fast artist updates
    pos = {node: G.nodes[node]['pos'] for node in G.nodes()}
    nodelist = list(G.nodes())
    node_xy = np.array([pos[n] for n in nodelist], dtype=float)
    node_values = np.array([G.nodes[n]['value'] for n in nodelist], dtype=float)
    edge_segments = []
    edge_values = []
    for u, v, attrs in G.edges(data=True):
        edge_segments.append([pos[u], pos[v]])
        edge_values.append(attrs["dvalue"])  # combined metric
    edge_values = np.array(edge_values, dtype=float)

    frames_data.append({
        'file_idx': file_idx,
        'nodes': G.number_of_nodes(),
        'edges': G.number_of_edges(),
        'node_xy': node_xy,
        'node_values': node_values,
        'edge_segments': edge_segments,
        'edge_values': edge_values,
        'matrix': final_matrix,
    })

    if (file_idx + 1) % 10 == 0 or file_idx == len(file_paths) - 1:
        print(f"  File {file_idx}: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

print(f"\nProcessed {len(frames_data)} valid frames")
print(f"Image dimensions: {image_h} x {image_w}")

# cell 2
import matplotlib as mpl
from matplotlib import cm, colors
import matplotlib.ticker as mticker

mpl.rcParams["animation.embed_limit"] = 80  # MB, increase as needed

# Use your project colormap
bluebrowngreen_cmap = ColorMaps()._bluebrowngreen_colormap

# =========================================================================
# HTML ANIMATION PLAYER (PLAY BUTTON + SCRUB BAR)
# =========================================================================
if len(frames_data) > 0:
    fig, ax = plt.subplots(figsize=(12, 6))

    margin_x = image_w * 0.05
    margin_y = image_h * 0.05
    ax.set_xlim(-margin_x, image_w + margin_x)
    ax.set_ylim(-margin_y, image_h + margin_y)
    ax.set_aspect('equal')
    ax.set_facecolor('white')

    # Initialize first frame
    init = frames_data[0]

    # Matrix background layer
    matrix_im = ax.imshow(
        init['matrix'],
        cmap=bluebrowngreen_cmap,
        alpha=0.3,
        vmin=matrix_min,
        vmax=matrix_max,
        extent=[0, image_w, 0, image_h],
        zorder=0,
        interpolation='nearest',
    )

    # Box around exact image limits
    image_box = plt.Rectangle(
        (0, 0),
        image_w,
        image_h,
        fill=False,
        edgecolor='black',
        linewidth=2.0,
        linestyle='-',
        zorder=3,
    )
    ax.add_patch(image_box)

    # Node colorbar mappable
    node_cmap = cm.get_cmap('gray')
    node_norm = colors.Normalize(vmin=min_value, vmax=max_value)
    node_sm = cm.ScalarMappable(norm=node_norm, cmap=node_cmap)
    node_sm.set_array([])

    # Edge colorbar mappable
    edge_cmap = cm.get_cmap('cool')
    non_empty_edge_arrays = [f['edge_values'] for f in frames_data if len(f['edge_values']) > 0]
    if non_empty_edge_arrays:
        all_edge_vals = np.concatenate(non_empty_edge_arrays)
        edge_min = float(all_edge_vals.min())
        edge_max = float(all_edge_vals.max())
    else:
        edge_min, edge_max = 0.0, 1.0

    edge_sm = cm.ScalarMappable(
        norm=colors.Normalize(vmin=edge_min, vmax=edge_max),
        cmap=edge_cmap,
    )
    edge_sm.set_array([])

    divider = make_axes_locatable(ax)
    cax_matrix = divider.append_axes('right', size='2.8%', pad=0.20)
    cax_nodes = divider.append_axes('right', size='2.8%', pad=1.20)
    cax_edges = divider.append_axes('right', size='2.8%', pad=1.40)

    cbar_matrix = fig.colorbar(matrix_im, cax=cax_matrix)
    cbar_matrix.set_label('Matrix value', rotation=270, labelpad=20, fontsize=15)

    cbar_nodes = fig.colorbar(node_sm, cax=cax_nodes)
    cbar_nodes.set_label('Node value', rotation=270, labelpad=20, fontsize=15)

    cbar_edges = fig.colorbar(edge_sm, cax=cax_edges)
    cbar_edges.set_label('Edge value', rotation=270, labelpad=20, fontsize=15)

    # Keep explicit top tick at edge_max
    if np.isclose(edge_min, edge_max):
        edge_ticks = np.array([edge_min])
    else:
        edge_ticks = np.linspace(edge_min, edge_max, 6)
        edge_ticks[-1] = edge_max
    cbar_edges.set_ticks(edge_ticks)
    cbar_edges.ax.yaxis.set_major_locator(mticker.FixedLocator(edge_ticks))
    cbar_edges.ax.set_ylim(edge_min, edge_max)

    artists = {'edges': None, 'nodes': None}

    def draw_graph_with_nx(data):
        if artists['edges'] is not None:
            artists['edges'].remove()
        if artists['nodes'] is not None:
            artists['nodes'].remove()

        Gf = nx.Graph()
        coords = [tuple(xy) for xy in data['node_xy']]
        Gf.add_nodes_from(coords)

        edge_list = [(tuple(seg[0]), tuple(seg[1])) for seg in data['edge_segments']]
        Gf.add_edges_from(edge_list)

        pos = {n: n for n in Gf.nodes()}
        values_by_coord = {tuple(xy): val for xy, val in zip(data['node_xy'], data['node_values'])}
        nodelist = list(Gf.nodes())
        node_colors = [values_by_coord[n] for n in nodelist]
        edge_colors = data['edge_values']

        artists['edges'] = nx.draw_networkx_edges(
            Gf,
            pos=pos,
            ax=ax,
            edge_color=edge_colors,
            edge_cmap=edge_cmap,
            edge_vmin=edge_min,
            edge_vmax=edge_max,
            width=2.5,
            alpha=0.8,
            hide_ticks=False,
        )

        artists['nodes'] = nx.draw_networkx_nodes(
            Gf,
            pos=pos,
            nodelist=nodelist,
            node_color=node_colors,
            cmap=node_cmap,
            vmin=min_value,
            vmax=max_value,
            node_size=2,
            ax=ax,
            hide_ticks=False,
        )

        major_step = 10
        ax.set_xticks(np.arange(0, image_w + 1, major_step))
        ax.set_yticks(np.arange(0, image_h + 1, major_step))
        ax.tick_params(axis='both', which='major', length=6, width=1.2, labelsize=14, direction='out')
        ax.grid(True, which='major', color='#b8c2cc', linestyle='--', linewidth=0.7, alpha=0.75)
        ax.set_xlabel('X (pixels)', fontsize=20)
        ax.set_ylabel('Y (pixels, flipped)', fontsize=20)

    draw_graph_with_nx(init)

    title = ax.set_title(
        f"Graph Evolution: Frame {init['file_idx']} | ({init['nodes']} nodes, {init['edges']} edges)",
        fontsize=16,
        pad=10,
    )
    fig.tight_layout()

    def update_plot(frame_idx):
        data = frames_data[frame_idx]
        matrix_im.set_data(data['matrix'])
        draw_graph_with_nx(data)
        title.set_text(
            f"Graph Evolution: Frame {data['file_idx']} | ({data['nodes']} nodes, {data['edges']} edges)"
        )
        return matrix_im, artists['edges'], artists['nodes'], title

    anim = animation.FuncAnimation(
        fig,
        update_plot,
        frames=len(frames_data),
        interval=220,
        blit=False,
        repeat=True,
    )

    display(HTML(anim.to_jshtml()))
    plt.close(fig)
    
#cell 3
from pathlib import Path
from matplotlib.animation import PillowWriter

gif_path = Path("output/rumney_marsh_rgb_a2/misc/graph_evolution.gif")
gif_path.parent.mkdir(parents=True, exist_ok=True)

# interval=220 ms -> about 4.5 fps (use 5)
anim.save(gif_path, writer=PillowWriter(fps=1), dpi=120)
print(f"Saved GIF to: {gif_path.resolve()}")