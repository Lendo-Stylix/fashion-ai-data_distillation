import matplotlib.pyplot as plt
import numpy as np
import os

# Set up styling and font
plt.style.use('ggplot')
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['figure.figsize'] = (10, 6)
plt.rcParams['font.size'] = 12

out_dir = r"docs\final_report_drafts"

if not os.path.exists(out_dir):
    os.makedirs(out_dir)

# 1. Funnel Chart
stages = ['Ban đầu (Raw)', 'Lọc DEITA (Complexity & Detail)', 'Lấy mẫu LIMA (Đa dạng hóa)', 'Cuối cùng (100% tiếng Việt)']
values = [10000, 4015, 1500, 1488]

plt.figure(figsize=(10, 6))
y_pos = np.arange(len(stages))
width = values
lefts = [(10000 - w) / 2 for w in width]

bars = plt.barh(y_pos, width, left=lefts, color=['#3498db', '#9b59b6', '#e74c3c', '#2ecc71'])
plt.yticks(y_pos, stages, fontweight='bold')
plt.gca().invert_yaxis()
plt.title('Biểu đồ Phễu Chưng Cất Dữ Liệu (Giai đoạn 1 -> 4)', fontweight='bold')
for i, bar in enumerate(bars):
    plt.text(bar.get_x() + bar.get_width()/2, bar.get_y() + bar.get_height()/2, 
             f'{values[i]} mẫu', ha='center', va='center', color='white', fontweight='bold', fontsize=12)
plt.axis('off')
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'phase1_to_4_data_funnel.png'), dpi=300)
plt.close()


# 2. DEITA Rubric Grouped Bar
labels = ['Complexity (Điểm >= 2)', 'Detail (Điểm 3 tuyệt đối)', 'Vocab (Điểm >= 2)']
# 10k dataset
comp_10k = 6704 + 1314
det_10k = 4540
voc_10k = 8305 + 1030

# DEITA dataset
comp_deita = 3068 + 947
det_deita = 4015
voc_deita = 3249 + 766

# LIMA dataset
comp_lima = 1135 + 353
det_lima = 1488
voc_lima = 1203 + 285

x = np.arange(len(labels))
width = 0.25

fig, ax = plt.subplots(figsize=(10, 6))
rects1 = ax.bar(x - width, [comp_10k, det_10k, voc_10k], width, label='10k Mẫu Gốc', color='#95a5a6')
rects2 = ax.bar(x, [comp_deita, det_deita, voc_deita], width, label='4k Mẫu DEITA', color='#3498db')
rects3 = ax.bar(x + width, [comp_lima, det_lima, voc_lima], width, label='1.4k Mẫu LIMA', color='#e74c3c')

ax.set_ylabel('Số lượng mẫu đạt chuẩn', fontweight='bold')
ax.set_title('Phân bổ Mẫu Đạt Điểm Chuẩn theo 3 Tiêu chí DEITA (Giai đoạn 1 -> 4)', fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(labels, fontweight='bold')
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'phase1_to_4_deita_lima_rubrics.png'), dpi=300)
plt.close()


# 3. Tag Distribution (Horizontal Bar)
tags = [
    'Kiến thức cơ bản', 'Hoàn cảnh', 'Dáng người', 'Phong cách', 
    'Mua sắm & Quản lý tủ đồ', 'Phong thái & Tâm lý', 
    'Bảo quản & Thời trang bền vững', 'Làm đẹp & Chăm sóc cá nhân'
]
percentages = [45.77, 28.63, 16.80, 5.85, 2.02, 0.47, 0.40, 0.07]
counts = [681, 426, 250, 87, 30, 7, 6, 1]

plt.figure(figsize=(12, 6))
y_pos = np.arange(len(tags))
bars = plt.barh(y_pos, percentages, color='#2ecc71')
plt.yticks(y_pos, tags, fontweight='bold')
plt.gca().invert_yaxis()
plt.xlabel('Tỷ lệ (%)', fontweight='bold')
plt.title('Hệ Thống Phân Loại - 8 Tags Cuối Cùng (Giai đoạn 4)', fontweight='bold')
for i, bar in enumerate(bars):
    plt.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, 
             f'{percentages[i]}% ({counts[i]} mẫu)', va='center')
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'phase4_tag_distribution.png'), dpi=300)
plt.close()


# 4. Verdict Distribution (Pie Chart)
labels = ['DATASET_SUPERIOR\n(Câu gốc: 40.3%)', 'CLOUD_SUPERIOR\n(Câu Cloud sinh: 36.9%)', 'VERIFIED_EQUAL\n(Tương đương: 22.8%)']
sizes = [600, 549, 339]
colors = ['#3498db', '#e74c3c', '#f1c40f']
explode = (0.05, 0, 0)

plt.figure(figsize=(8, 8))
plt.pie(sizes, explode=explode, labels=labels, colors=colors, autopct=lambda p: '{:.0f}'.format(p * sum(sizes) / 100),
        shadow=True, startangle=140, textprops={'fontsize': 12, 'fontweight': 'bold'})
plt.title('Phân phối Đánh giá Chất lượng - Verdict (Giai đoạn 5)', fontweight='bold', fontsize=14)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'phase5_verdict_distribution.png'), dpi=300)
plt.close()


# 5. Final Answer Source Chart (Donut Chart)
labels = ['Sử dụng A_Cloud\n(59.7%)', 'Sử dụng A_Dataset\n(40.3%)']
sizes = [888, 600]
colors = ['#e74c3c', '#3498db']

plt.figure(figsize=(8, 8))
plt.pie(sizes, labels=labels, colors=colors, autopct=lambda p: '{:.0f} mẫu'.format(p * sum(sizes) / 100), 
        startangle=90, textprops={'fontsize': 13, 'fontweight': 'bold'}, pctdistance=0.75)
centre_circle = plt.Circle((0,0), 0.60, fc='white')
fig = plt.gcf()
fig.gca().add_artist(centre_circle)
plt.title('Nguồn Câu Trả Lời Cuối Cùng Được Chọn - A_Final (Giai đoạn 5)', fontweight='bold', fontsize=14)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'phase5_a_final_source.png'), dpi=300)
plt.close()

print("Charts successfully generated in docs/final_report_drafts/")
