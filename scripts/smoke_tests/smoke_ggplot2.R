# smoke_ggplot2.R -- Smoke test for ggplot2 + extensions
# Validates: ggplot2, scales, patchwork, ggrepel, ggridges, ggdist
# All plots saved to temp files, verified, then cleaned up.

# --- Config ---
library(ggplot2)
library(scales)
library(patchwork)
library(ggrepel)
library(ggridges)
library(ggdist)

cat("=== ggplot2 Smoke Test ===\n\n")

# --- Test 1: Version checks ---
cat("Test 1: Version checks\n")
ggplot2_ver <- as.character(packageVersion("ggplot2"))
scales_ver <- as.character(packageVersion("scales"))
patchwork_ver <- as.character(packageVersion("patchwork"))
ggrepel_ver <- as.character(packageVersion("ggrepel"))
ggridges_ver <- as.character(packageVersion("ggridges"))
ggdist_ver <- as.character(packageVersion("ggdist"))

cat("  ggplot2:", ggplot2_ver, "\n")
cat("  scales:", scales_ver, "\n")
cat("  patchwork:", patchwork_ver, "\n")
cat("  ggrepel:", ggrepel_ver, "\n")
cat("  ggridges:", ggridges_ver, "\n")
cat("  ggdist:", ggdist_ver, "\n")

stopifnot(numeric_version(ggplot2_ver) >= "4.0.0")
stopifnot(numeric_version(scales_ver) >= "1.4.0")
stopifnot(numeric_version(patchwork_ver) >= "1.3.0")
cat("  PASS: All versions meet minimum requirements\n\n")

# --- Test 2: Basic scatter + smooth ---
cat("Test 2: geom_point() + geom_smooth()\n")
tmp2 <- tempfile(fileext = ".png")
p2 <- ggplot(mtcars, aes(x = wt, y = mpg)) +
  geom_point(size = 2) +
  geom_smooth(method = "lm", se = TRUE, linewidth = 0.8) +
  labs(title = "Scatter + Smooth") +
  theme_minimal()
ggsave(tmp2, p2, width = 8, height = 6, dpi = 150)
stopifnot(file.exists(tmp2))
stopifnot(file.info(tmp2)$size > 0)
file.remove(tmp2)
cat("  PASS\n\n")

# --- Test 3: geom_bar() + geom_col() ---
cat("Test 3: geom_bar() + geom_col()\n")
tmp3a <- tempfile(fileext = ".png")
p3a <- ggplot(mtcars, aes(x = factor(cyl))) +
  geom_bar(fill = "steelblue") +
  labs(title = "geom_bar (count)") +
  theme_minimal()
ggsave(tmp3a, p3a, width = 6, height = 4, dpi = 150)
stopifnot(file.exists(tmp3a))

tmp3b <- tempfile(fileext = ".png")
bar_data <- data.frame(
  category = c("A", "B", "C"),
  value = c(10, 25, 15)
)
p3b <- ggplot(bar_data, aes(x = category, y = value)) +
  geom_col(fill = "coral", linewidth = 0.5, color = "black") +
  labs(title = "geom_col (values)") +
  theme_minimal()
ggsave(tmp3b, p3b, width = 6, height = 4, dpi = 150)
stopifnot(file.exists(tmp3b))
file.remove(tmp3a, tmp3b)
cat("  PASS\n\n")

# --- Test 4: geom_histogram() + geom_density() ---
cat("Test 4: geom_histogram() + geom_density()\n")
tmp4 <- tempfile(fileext = ".png")
p4 <- ggplot(mtcars, aes(x = mpg)) +
  geom_histogram(aes(y = after_stat(density)), bins = 15, fill = "grey70") +
  geom_density(color = "red", linewidth = 1) +
  labs(title = "Histogram + Density") +
  theme_minimal()
ggsave(tmp4, p4, width = 6, height = 4, dpi = 150)
stopifnot(file.exists(tmp4))
file.remove(tmp4)
cat("  PASS\n\n")

# --- Test 5: facet_wrap() + facet_grid() ---
cat("Test 5: facet_wrap() + facet_grid()\n")
tmp5a <- tempfile(fileext = ".png")
p5a <- ggplot(mtcars, aes(x = wt, y = mpg)) +
  geom_point() +
  facet_wrap(~ cyl, ncol = 3) +
  labs(title = "facet_wrap") +
  theme_minimal()
ggsave(tmp5a, p5a, width = 10, height = 4, dpi = 150)
stopifnot(file.exists(tmp5a))

tmp5b <- tempfile(fileext = ".png")
p5b <- ggplot(mtcars, aes(x = wt, y = mpg)) +
  geom_point() +
  facet_grid(am ~ cyl) +
  labs(title = "facet_grid") +
  theme_minimal()
ggsave(tmp5b, p5b, width = 10, height = 6, dpi = 150)
stopifnot(file.exists(tmp5b))
file.remove(tmp5a, tmp5b)
cat("  PASS\n\n")

# --- Test 6: scale_*_continuous() + scale_color_viridis_d() ---
cat("Test 6: Scales customization\n")
tmp6 <- tempfile(fileext = ".png")
p6 <- ggplot(mtcars, aes(x = wt, y = mpg, color = factor(cyl))) +
  geom_point(size = 3) +
  scale_x_continuous(breaks = seq(1, 6, by = 1)) +
  scale_y_continuous(labels = label_comma()) +
  scale_color_viridis_d(option = "plasma") +
  labs(title = "Scales Test", color = "Cylinders") +
  theme_minimal()
ggsave(tmp6, p6, width = 8, height = 6, dpi = 150)
stopifnot(file.exists(tmp6))
file.remove(tmp6)
cat("  PASS\n\n")

# --- Test 7: theme_minimal() + custom theme() ---
cat("Test 7: Theming\n")
tmp7 <- tempfile(fileext = ".png")
p7 <- ggplot(mtcars, aes(x = wt, y = mpg)) +
  geom_point() +
  labs(title = "Custom Theme Test", subtitle = "With modifications") +
  theme_minimal(base_size = 14) +
  theme(
    plot.title = element_text(face = "bold", size = 18),
    plot.subtitle = element_text(color = "grey40"),
    axis.text.x = element_text(angle = 45, hjust = 1),
    panel.grid.minor = element_blank(),
    legend.position = "bottom"
  )
ggsave(tmp7, p7, width = 8, height = 6, dpi = 150)
stopifnot(file.exists(tmp7))
file.remove(tmp7)
cat("  PASS\n\n")

# --- Test 8: ggsave() to PNG ---
cat("Test 8: ggsave() export\n")
tmp8 <- tempfile(fileext = ".png")
p8 <- ggplot(mtcars, aes(x = hp, y = mpg)) +
  geom_point() +
  theme_bw()
ggsave(tmp8, p8, width = 10, height = 8, dpi = 300)
stopifnot(file.exists(tmp8))
fsize <- file.info(tmp8)$size
cat("  File size:", fsize, "bytes\n")
stopifnot(fsize > 10000)
file.remove(tmp8)
cat("  PASS\n\n")

# --- Test 9: patchwork composition ---
cat("Test 9: patchwork (p1 + p2)\n")
tmp9 <- tempfile(fileext = ".png")
pa <- ggplot(mtcars, aes(x = wt, y = mpg)) +
  geom_point() + labs(title = "A") + theme_minimal()
pb <- ggplot(mtcars, aes(x = factor(cyl))) +
  geom_bar(fill = "steelblue") + labs(title = "B") + theme_minimal()
combined <- (pa | pb) +
  plot_annotation(title = "Patchwork Test", tag_levels = "A")
ggsave(tmp9, combined, width = 12, height = 5, dpi = 150)
stopifnot(file.exists(tmp9))
file.remove(tmp9)
cat("  PASS\n\n")

# --- Test 10: ggrepel ---
cat("Test 10: ggrepel::geom_text_repel()\n")
tmp10 <- tempfile(fileext = ".png")
top_cars <- head(mtcars[order(-mtcars$mpg), ], 5)
top_cars$name <- rownames(top_cars)
p10 <- ggplot(mtcars, aes(x = wt, y = mpg)) +
  geom_point(color = "grey60") +
  geom_point(data = top_cars, color = "red", size = 3) +
  geom_text_repel(data = top_cars, aes(label = name), seed = 42) +
  labs(title = "ggrepel Test") +
  theme_minimal()
ggsave(tmp10, p10, width = 8, height = 6, dpi = 150)
stopifnot(file.exists(tmp10))
file.remove(tmp10)
cat("  PASS\n\n")

# --- Summary ---
cat("=== All 10 tests PASSED ===\n")
cat("Tested: ggplot2", ggplot2_ver, "/ scales", scales_ver,
    "/ patchwork", patchwork_ver, "\n")
cat("        ggrepel", ggrepel_ver, "/ ggridges", ggridges_ver,
    "/ ggdist", ggdist_ver, "\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-05-08 22:17:48
# Command: Rscript /daaf/scripts/smoke_tests/smoke_ggplot2.R
# Duration: 2s
# Exit code: 0
#
# --- STDOUT ---
# 
# Attaching package: ‘ggdist’
# 
# The following objects are masked from ‘package:ggridges’:
# 
#     scale_point_color_continuous, scale_point_color_discrete,
#     scale_point_colour_continuous, scale_point_colour_discrete,
#     scale_point_fill_continuous, scale_point_fill_discrete,
#     scale_point_size_continuous
# 
# === ggplot2 Smoke Test ===
# 
# Test 1: Version checks
#   ggplot2: 4.0.2 
#   scales: 1.4.0 
#   patchwork: 1.3.2 
#   ggrepel: 0.9.8 
#   ggridges: 0.5.7 
#   ggdist: 3.3.3 
#   PASS: All versions meet minimum requirements
# 
# Test 2: geom_point() + geom_smooth()
# `geom_smooth()` using formula = 'y ~ x'
# [1] TRUE
#   PASS
# 
# Test 3: geom_bar() + geom_col()
# [1] TRUE TRUE
#   PASS
# 
# Test 4: geom_histogram() + geom_density()
# [1] TRUE
#   PASS
# 
# Test 5: facet_wrap() + facet_grid()
# [1] TRUE TRUE
#   PASS
# 
# Test 6: Scales customization
# [1] TRUE
#   PASS
# 
# Test 7: Theming
# [1] TRUE
#   PASS
# 
# Test 8: ggsave() export
#   File size: 58698 bytes
# [1] TRUE
#   PASS
# 
# Test 9: patchwork (p1 + p2)
# [1] TRUE
#   PASS
# 
# Test 10: ggrepel::geom_text_repel()
# [1] TRUE
#   PASS
# 
# === All 10 tests PASSED ===
# Tested: ggplot2 4.0.2 / scales 1.4.0 / patchwork 1.3.2 
#         ggrepel 0.9.8 / ggridges 0.5.7 / ggdist 3.3.3 
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
