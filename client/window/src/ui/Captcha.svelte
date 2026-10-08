<script lang="ts">
  /* KFintech's captcha, asked in place: a big image, one field, Enter continues, "Can't read it? New image". */
  import { onMount } from 'svelte';

  let { image, message = '', onanswer }: { image: string; message?: string; onanswer: (text: string, refresh: boolean) => void } = $props();
  let text = $state('');
  let field: HTMLInputElement;
  onMount(() => setTimeout(() => field?.focus(), 50));
  $effect(() => { void image; text = ''; field?.focus(); });

  const go = () => { if (text.trim()) onanswer(text.trim(), false); };
</script>

<div class="capbox enter">
  <b>Type the characters from KFintech.</b>
  <div class="captcha-img"><img src={image} alt="The characters to type" /></div>
  <div class="caprow">
    <input bind:this={field} bind:value={text} class="input mono" autocomplete="off" spellcheck="false" style="max-width:200px"
      aria-label="The characters" data-own-enter onkeydown={e => { if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); go(); } }} />
    <button class="btn primary" disabled={!text.trim()} onclick={go}>Continue</button>
    <a href="#new" onclick={e => { e.preventDefault(); onanswer('', true); }}>Can't read it? New image</a>
  </div>
  {#if message}<span class="err" style="font-size:12.5px">{message}</span>{/if}
</div>
