'use strict';
const $ = id => document.getElementById(id);
let config;
const reasons = {
  question_company_conflicts_with_scope:'The question names a different company from the selected filing.',
  question_period_conflicts_with_scope:'The requested reporting date is outside the selected filings.',
  question_year_conflicts_with_scope:'The requested year is outside the selected reporting periods.',
  question_form_conflicts_with_scope:'The requested filing form is not selected or available.',
  unsupported_prediction_or_advice:'These filings cannot support a prediction or an investment recommendation.',
  requested_date_precision_not_disclosed:'The filing does not disclose the exact date requested.',
  requested_number_not_supported:'The requested number is not supported by the retrieved evidence.',
  requested_precision_not_disclosed:'The evidence does not support that degree of precision.',
  no_currency_amount_in_evidence:'The retrieved passage does not disclose the requested monetary amount.',
  no_explicit_causal_evidence:'A related passage was found, but it does not establish the requested cause.',
  hypothetical_risk_not_realized_cause:'A possible risk does not establish that an event occurred.',
  question_details_not_supported:'The retrieved evidence does not support every detail in this question.',
  insufficient_topic_support:'The retrieved passages do not provide enough support for this question.'
};
function node(tag,text,className){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e;}
function refreshFilings(){
  const docs=config.documents.filter(d=>d.ticker===$('company').value);
  $('filing').replaceChildren(...docs.map(d=>{const o=node('option',`${d.form} · period ${d.report_period} · filed ${d.filing_date}`);o.value=d.accession;return o;}));
  $('compare').disabled=docs.length!==2;
  $('example').textContent=$('company').value==='DOCU'?'Why did revenue increase?':'Compare total liquidity disclosed in the two filings.';
}
async function api(path,body){const r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const data=await r.json();if(!r.ok)throw new Error(data.error||'Request failed');return data;}
async function showSource(id){
  try{
    const data=await api('/api/passage?id='+encodeURIComponent(id));const p=data.selected;
    $('source-meta').textContent=`${p.company} · ${p.form} · ${p.section.toUpperCase()} · Report period ${p.report_period} · Filed ${p.filing_date}\nAccession ${p.accession}\nSHA-256 ${p.sha256}\nNormalized narrative characters ${p.start_char}–${p.end_char}`;
    $('source-context').replaceChildren(...data.context.map(c=>{const para=node('p');if(c.passage_id===id)para.append(node('mark',c.text));else para.textContent=c.text;return para;}));
    $('original').href=p.source_url+(p.anchor?'#'+encodeURIComponent(p.anchor):'');
    $('source-dialog').showModal();
  }catch(error){$('results').append(node('p',error.message,'abstention'));}
}
$('close-source').addEventListener('click',()=>$('source-dialog').close());
$('compare').addEventListener('change',()=>{$('filing').disabled=$('compare').checked;$('comparison-note').textContent=$('compare').checked?'Both reporting periods will appear side by side. No change is calculated.':'Reporting dates and filing dates are shown separately.';});
$('company').addEventListener('change',refreshFilings);
$('example').addEventListener('click',()=>{$('question').value=$('example').textContent;$('compare').checked=$('company').value==='AIN';$('compare').dispatchEvent(new Event('change'));if($('company').value==='DOCU')$('filing').value=config.documents.find(d=>d.ticker==='DOCU'&&d.form==='10-Q').accession;$('question').focus();});
$('research').addEventListener('submit',async event=>{
  event.preventDefault();$('submit').disabled=true;$('results').setAttribute('aria-busy','true');$('results').replaceChildren(node('p','Finding evidence in the selected filings…','hint'));
  try{
    const compare=$('compare').checked;
    const accessions=compare?config.documents.filter(d=>d.ticker===$('company').value).map(d=>d.accession):[$('filing').value];
    const r=await api('/api/ask',{question:$('question').value,scope:{company:$('company').value,accessions,section:$('section').value||null},compare,method:$('method').value});
    $('results').replaceChildren();
    if(r.status==='abstained'){
      const box=node('div',undefined,'abstention');box.append(node('strong','No supported answer'),node('p',reasons[r.reason]||'This question cannot be established from the selected narrative passages.'),node('p','Try a narrower question or choose a different filing or section.','hint'));$('results').append(box);
    }else{
      $('results').append(node('h2',compare?'Two filings. Source by source.':'Evidence from the filing'));
      if(compare)$('results').append(node('p','These are disclosed periods, not necessarily comparable durations. No arithmetic or inferred change is presented.','hint'));
      const cards=node('div',undefined,'cards');
      r.answer.forEach(a=>{const c=a.citation,card=node('article',undefined,'card');card.append(node('h3',`${c.company} · ${c.form}`),node('p',`Report period ${c.report_period} · Filed ${c.filing_date}\n${c.section.toUpperCase()} · ${c.accession}`,'meta'),node('p',a.excerpt,'excerpt'));const button=node('button','Inspect source ↗');button.type='button';button.addEventListener('click',()=>showSource(c.passage_id));card.append(button);cards.append(card);});
      $('results').append(cards,node('p','Verbatim narrative extracts. Relevance checks are heuristic; review the original disclosure before relying on a claim.','hint'));
    }
  }catch(error){$('results').replaceChildren(node('p',error.message,'abstention'));}
  finally{$('submit').disabled=false;$('results').setAttribute('aria-busy','false');}
});
api('/api/config').then(data=>{config=data;const companies=[...new Map(data.documents.map(d=>[d.ticker,d])).values()];$('company').replaceChildren(...companies.map(d=>{const o=node('option',d.company+' · '+d.ticker);o.value=d.ticker;return o;}));$('notice').textContent=`${data.documents.length} real filings · ${data.passages.toLocaleString()} passages. ${data.notice}`;refreshFilings();}).catch(error=>{$('results').textContent=error.message;$('submit').disabled=true;});
