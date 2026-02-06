<script lang="ts">
  import "../app.css";

  interface Props {
    children: import("svelte").Snippet;
  }

  let { children }: Props = $props();
</script>

<div class="min-h-screen reader-bg flex flex-col">
  <div class="flex-1">
    {@render children()}
  </div>

  <footer class="py-6 text-center text-gray-400 text-sm">
    <p>AudioBook App v2.1</p>
  </footer>
</div>
