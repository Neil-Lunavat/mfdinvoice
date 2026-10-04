<script lang="ts">
  import { NAME } from '../brand';
  import { icons } from '../ui/icons';
</script>

<div class="view splash" role="status" aria-label="Starting">
  <span class="mark">{@html icons.mark(30)}</span>
  <div class="name">{NAME}</div>
  <div class="line"><span class="spin"></span>Starting</div>
</div>
