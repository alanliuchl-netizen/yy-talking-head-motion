#!/usr/bin/env python3
"""Verify the delivered MP4 and extract actual cut/scene/caption frames for review."""
import argparse
import json
import math
import re
import subprocess
from pathlib import Path
from verify import verify


def _run(args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode: raise RuntimeError(result.stderr[-5000:])
    return result


def frame_targets(project, edit=None):
    fps, duration = project['fps'], project['duration']
    points = [(0, 'opening'), (max(0, duration-1/fps), 'ending')]
    for scene in project['scenes']:
        points.append((min(duration-1/fps, scene['start']+.8), 'scene:'+scene['id']))
    if edit:
        for clip in edit['timeline'][1:]:
            points.extend([(max(0, clip['start']-1/fps), 'before-cut:'+clip['id']),
                           (min(duration-1/fps, clip['start']+1/fps), 'after-cut:'+clip['id'])])
    for i, cue in sorted(enumerate(project['captions']), key=lambda x: len(x[1]['text']), reverse=True)[:4]:
        points.append(((cue['start']+cue['end'])/2, 'long-caption:'+str(i+1)))
    grouped = {}
    for time, label in points:
        frame = min(round(time*fps), max(0, round(duration*fps)-1))
        grouped.setdefault(frame, []).append(label)
    return [{'frame': frame, 'time': frame/fps, 'reasons': grouped[frame]} for frame in sorted(grouped)]


def review(video, project_path, output, edit_path=None, roundtrip_path=None):
    video, project_path, output = Path(video).resolve(), Path(project_path).resolve(), Path(output)
    if output.exists() or output.is_symlink(): raise FileExistsError('Review directory exists; choose a new one')
    project = json.loads(project_path.read_text()); edit = json.loads(Path(edit_path).read_text()) if edit_path else None
    audio = project['media'].get('audio_copy')
    reference = (project_path.parent/audio).resolve() if audio else None
    if reference and project_path.parent not in reference.parents: raise ValueError('Audio reference escapes project')
    technical = verify(video, project_path, reference)
    if edit:
        if abs(edit['duration']-project['duration']) > 1e-6 or edit['fps'] != project['fps']:
            raise ValueError('Motion project does not match the edited timeline')
        if edit['captions'] != project['captions']:
            raise ValueError('Packaging changed the edited captions/timing')
    measured = _run(['ffmpeg', '-hide_banner', '-i', str(video), '-vn', '-af',
                     'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-']).stderr
    match = re.search(r'\{\s*"input_i".*?\}', measured, re.S)
    if not match: raise ValueError('Delivered audio loudness unavailable')
    values = json.loads(match.group())
    integrated, peak = float(values['input_i']), float(values['input_tp'])
    if not math.isfinite(integrated) or not math.isfinite(peak): raise ValueError('Delivered audio has no measurable sound')
    issues = []
    normalization_applied = bool(edit and edit.get('loudness', {}).get('applied'))
    if normalization_applied and (abs(integrated+16)>1.5 or peak > -1.0):
        issues.append('Delivered normalized audio is outside -16±1.5 LUFS / ≤-1 dBTP')
    roundtrip = json.loads(Path(roundtrip_path).read_text()) if roundtrip_path else None
    if roundtrip and roundtrip.get('video_sha256') != technical['sha256']:
        raise ValueError('Roundtrip report belongs to a different video')
    if roundtrip and roundtrip.get('status') != 'PASS': issues.append('Speech roundtrip has mismatches requiring review')
    if edit and edit['status']=='needs_review': issues.append('Edit plan has unresolved transcript/semantic findings')
    output.mkdir(parents=True, exist_ok=False); frames = output/'frames'; frames.mkdir()
    targets = frame_targets(project, edit)
    for index, point in enumerate(targets):
        name = f'{index:04d}.jpg'; point['file']='frames/'+name
        _run(['ffmpeg','-v','error','-n','-ss',f'{point["time"]:.9f}','-i',str(video),
              '-frames:v','1','-q:v','2',str(frames/name)])
    sheets=[]
    for page in range(math.ceil(len(targets)/12)):
        count=min(12,len(targets)-page*12);name=f'frames-{page+1:02d}.jpg'
        _run(['ffmpeg','-v','error','-n','-framerate','1','-start_number',str(page*12),
              '-i',str(frames/'%04d.jpg'),'-vf',
              f'scale=360:640:force_original_aspect_ratio=decrease,pad=360:640:(ow-iw)/2:(oh-ih)/2,'
              f'tile=4x3:nb_frames={count}:padding=6:margin=6',
              '-frames:v','1','-q:v','3',str(output/name)])
        sheets.append(name)
    report={'status':'NEEDS_REVIEW' if issues else 'TECHNICAL_PASS_REVIEW_PENDING',
            'video_sha256':technical['sha256'],'technical':technical,
            'captions_match_edit':True if edit else 'not compared',
            'loudness':{'integrated_lufs':integrated,'true_peak_db':peak,
                        'normalization_applied':normalization_applied},
            'speech_roundtrip':roundtrip or 'not performed','issues':issues,
            'cut_risks':edit.get('cut_risks',[]) if edit else [],
            'frames':targets,'contact_sheets':sheets,
            'full_av_review':'not performed by this script',
            'semantic_review':'Agent must review actual output order, facts, qualifiers and referents',
            'limits':'Technical/audio measurements and extracted frames do not prove transcript truth or publish readiness.'}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video',required=True,type=Path)
    parser.add_argument('--project',required=True,type=Path)
    parser.add_argument('--edit',type=Path)
    parser.add_argument('--roundtrip',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    report=review(args.video,args.project,args.output,args.edit,args.roundtrip)
    print(json.dumps({key:report[key] for key in ('status','loudness','issues','contact_sheets','full_av_review')},
                     ensure_ascii=False,indent=2))


if __name__=='__main__':main()
