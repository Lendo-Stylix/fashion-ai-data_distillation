import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os

# Setting up the figure
fig, ax = plt.subplots(figsize=(10, 12))
ax.axis('off')

# Defining phases
phases = [
    ('Giai doan 1 & 2: Data Cleaning', 'Loc DEITA (Complexity/Detail/Vocab)\n10.000 -> 4.015 mau'),
    ('Giai doan 3: Phan loai & LIMA', 'Loc LIMA & Gan 8 Tags Thoi trang\n4.015 -> 1.488 mau'),
    ('Giai doan 4: Dich Thuat', 'Gemini 2.0 Flash (Eng -> Viet)\nDam bao ngu canh thoi trang'),
    ('Giai doan 5: Sinh The <think>', 'DeepSeek-R1 Distillation\nTao luong tu duy (CoT)'),
    ('Giai doan 6: Chuan bi Finetune', 'Stratified Grouping & ChatML\nTao batch dong nhat (16 mau/batch)'),
    ('Giai doan 7: Fine-Tuning', 'Qwen 3.5 4B + LoRA + Unsloth\nTrain on Responses (3 Epochs)')
]

y_start = 0.9
box_height = 0.08
box_width = 0.6
y_gap = 0.14

for i, (title, desc) in enumerate(phases):
    y = y_start - i * y_gap
    # Draw box
    box = patches.FancyBboxPatch(
        (0.2, y - box_height/2), box_width, box_height,
        boxstyle='round,pad=0.03', ec='#1f77b4', fc='#e3f2fd', lw=2
    )
    ax.add_patch(box)
    
    # Add text
    ax.text(0.5, y + 0.015, title, ha='center', va='center', fontsize=12, fontweight='bold', color='#0d47a1')
    ax.text(0.5, y - 0.02, desc, ha='center', va='center', fontsize=10, color='#333333')
    
    # Add arrow to next box
    if i < len(phases) - 1:
        arrow_y_start = y - box_height/2 - 0.03
        arrow_y_end = arrow_y_start - (y_gap - box_height - 0.03) + 0.03
        ax.annotate('', xy=(0.5, arrow_y_end), xytext=(0.5, arrow_y_start),
                    arrowprops=dict(facecolor='#1f77b4', edgecolor='none', width=3, headwidth=10))

plt.title('Fashion AI: Reasoning Data Pipeline', fontsize=16, fontweight='bold', pad=20)
plt.tight_layout()

# Save the plot
output_path = os.path.join('docs', 'final_report_drafts', 'Pipeline_Flowchart.png')
plt.savefig(output_path, bbox_inches='tight', dpi=300)
print(f"Chart saved to {output_path}")
