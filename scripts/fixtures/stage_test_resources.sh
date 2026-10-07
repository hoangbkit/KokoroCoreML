#!/bin/bash
set -euo pipefail

# Xcode copies package resources into the hostless test bundle, but Misaki is
# a dynamic framework: its generated Bundle.module accessor searches the
# framework's Resources directory. Stage only this temporary test build.
build_products="${1:?Usage: stage_test_resources.sh /path/to/Build/Products/Debug}"
framework_resources="$build_products/PackageFrameworks/MisakiSwift.framework/Resources"
misaki_bundle="$build_products/MisakiSwift_MisakiSwift.bundle"
mlx_bundle="$build_products/mlx-swift_Cmlx.bundle"
metallib="$mlx_bundle/Contents/Resources/default.metallib"

if [[ ! -d "$framework_resources" ||
      ! -s "$misaki_bundle/Contents/Resources/MisakiData/us_gold.json" ||
      ! -s "$misaki_bundle/Contents/Resources/MisakiData/us_bart.safetensors" ||
      ! -s "$metallib" ]]; then
    echo 'Missing built Misaki framework, language data, or MLX Metal library' >&2
    exit 1
fi

/usr/bin/ditto "$misaki_bundle" "$framework_resources/MisakiSwift_MisakiSwift.bundle"
/usr/bin/ditto "$mlx_bundle" "$framework_resources/mlx-swift_Cmlx.bundle"
# MLX also explicitly supports Resources/default.metallib beside its dynamic
# binary. Preserve that fallback instead of depending on test-host discovery.
cp "$metallib" "$framework_resources/default.metallib"
echo "Staged Misaki data and MLX shaders in $framework_resources"
