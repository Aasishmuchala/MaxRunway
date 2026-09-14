"""3ds Max 2026 / PySide6 panel. Render on main thread; MCP in a child process."""
import json
import os
import shutil
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
from pymxs import runtime as rt
from qtmax import GetQMaxMainWindow

from . import native
from .jobs import create_job
from .settings import (CredentialStore, OMEGA_MODELS, codex_path, launch_codex,
                       load_settings, run_codex, save_settings)

ROOT = Path(__file__).resolve().parents[1]
_panel = None


class Panel(QtWidgets.QDockWidget):
    def __init__(self, parent):
        super().__init__('MaxRunway · Cinematic 4K', parent)
        self.setObjectName('MaxRunwayCinematic')
        self.job_path = None
        self.rendering = False
        self.stop_requested = False
        self.process = None
        self.process_action = None
        self.stdout_buffer = ''
        self.stderr_buffer = ''
        self.preferences = load_settings()
        self.credentials = CredentialStore()
        content = QtWidgets.QWidget()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        self.setWidget(scroll)
        layout = QtWidgets.QVBoxLayout(content)
        self.subtitle = QtWidgets.QLabel('3ds Max 2026 · V-Ray 7.x · Runway MCP · MaxRunway 0.2.0')
        layout.addWidget(self.subtitle)
        note = QtWidgets.QLabel('Native EXR masters retain the V-Ray render. AI versions can alter textures, reflections, geometry, and camera timing—even at 4K.')
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QtWidgets.QFormLayout()
        layout.addLayout(form)
        self.camera = QtWidgets.QComboBox()
        form.addRow('Camera', self.camera)
        self.mode = QtWidgets.QComboBox()
        self.mode.addItem('Full-rate 640×360 camera guide + sparse V-Ray 4K anchors → Runway 4K', 'guided')
        self.mode.addItem('Animate one V-Ray frame → Runway 4K', 'image')
        self.mode.addItem('Render cinematic → Runway 4K variation', 'video')
        self.mode.addItem('Native V-Ray 4K sequence only', 'native')
        form.addRow('Workflow', self.mode)
        self.first = QtWidgets.QSpinBox()
        self.last = QtWidgets.QSpinBox()
        for box in (self.first, self.last):
            box.setRange(-100000, 100000)
        self.first.setValue(int(rt.animationRange.start.frame))
        self.last.setValue(int(rt.animationRange.end.frame))
        row = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.first)
        row_layout.addWidget(QtWidgets.QLabel('to'))
        row_layout.addWidget(self.last)
        form.addRow('Scene frames', row)
        self.duration = QtWidgets.QSpinBox()
        self.duration.setRange(4, 15)
        self.duration.setValue(5)
        self.duration.setSuffix(' s')
        form.addRow('AI still duration', self.duration)
        self.anchor_count = QtWidgets.QSpinBox()
        self.anchor_count.setRange(2, 9)
        self.anchor_count.setValue(8)
        form.addRow('Native 4K anchors', self.anchor_count)
        self.loop_shot = QtWidgets.QCheckBox('Circle / loop shot (final pose repeats the first)')
        form.addRow('', self.loop_shot)
        self.timing = QtWidgets.QLabel()
        self.timing.setWordWrap(True)
        form.addRow('Timing', self.timing)
        self.prompt = QtWidgets.QPlainTextEdit()
        self.prompt.setPlaceholderText('Describe camera motion, pacing, and scene movement.')
        self.prompt.setPlainText('A slow, steady cinematic push forward. Gentle natural movement in the vegetation. Keep the architecture, surface patterns, and lighting consistent with the reference.')
        self.prompt.setMaximumHeight(110)
        form.addRow('Motion prompt', self.prompt)
        output_row = QtWidgets.QWidget()
        output_layout = QtWidgets.QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        self.output = QtWidgets.QLineEdit(str(ROOT / 'renders'))
        choose = QtWidgets.QPushButton('Browse')
        choose.clicked.connect(self.choose_output)
        output_layout.addWidget(self.output)
        output_layout.addWidget(choose)
        form.addRow('Job folder', output_row)
        self.refresh_button = QtWidgets.QPushButton('Refresh scene cameras')
        self.refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_button)
        self.connect_button = QtWidgets.QPushButton('Connect Runway (browser sign-in)')
        self.connect_button.clicked.connect(lambda: self.start_bridge('connect'))
        layout.addWidget(self.connect_button)
        self.export_button = QtWidgets.QPushButton('1. Render native reference at 3840 × 2160')
        self.export_button.clicked.connect(self.export)
        layout.addWidget(self.export_button)
        self.stop_button = QtWidgets.QPushButton('Stop after current frame · Esc cancels current render')
        self.stop_button.clicked.connect(self.stop_render)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)
        self.preview_button = QtWidgets.QPushButton('2. Open reference for review')
        self.preview_button.clicked.connect(self.open_reference)
        layout.addWidget(self.preview_button)
        self.reviewed = QtWidgets.QCheckBox('I reviewed the guide and every 4K anchor, including colour and exposure')
        self.reviewed.toggled.connect(self.update_actions)
        layout.addWidget(self.reviewed)
        self.submit_button = QtWidgets.QPushButton('3. Send to Runway · creates a paid 4K generation')
        self.submit_button.clicked.connect(lambda: self.start_bridge('submit', self.job_path))
        layout.addWidget(self.submit_button)
        load = QtWidgets.QPushButton('Load saved job / resume Runway task')
        load.clicked.connect(self.load_job)
        self.load_button = load
        layout.addWidget(load)
        self.result_button = QtWidgets.QPushButton('Open finished video / job folder')
        self.result_button.clicked.connect(self.open_result)
        layout.addWidget(self.result_button)

        lighting_group = QtWidgets.QGroupBox('IMPACT-inspired lighting recipes · preview only')
        lighting_layout = QtWidgets.QVBoxLayout(lighting_group)
        self.lighting_recipe = QtWidgets.QComboBox()
        self.lighting_details = QtWidgets.QPlainTextEdit()
        self.lighting_details.setReadOnly(True)
        self.lighting_details.setMaximumHeight(125)
        lighting_open = QtWidgets.QPushButton('Open full lighting recipe and acceptance guide')
        lighting_open.clicked.connect(self.open_lighting_guide)
        try:
            self.lighting_data = json.loads((ROOT / 'presets/IMPACT-Inspired-Lighting-Presets.json').read_text(encoding='utf-8'))
            for recipe in self.lighting_data.get('presets', []):
                self.lighting_recipe.addItem('%s · %s' % (recipe['id'], recipe['name']), recipe)
        except Exception as exc:
            self.lighting_data = {}
            self.lighting_recipe.addItem('Preset library unavailable: ' + str(exc), None)
        self.lighting_recipe.currentIndexChanged.connect(self.update_lighting_recipe)
        lighting_layout.addWidget(self.lighting_recipe)
        lighting_layout.addWidget(self.lighting_details)
        lighting_layout.addWidget(lighting_open)
        lighting_warning = QtWidgets.QLabel('Recipes never auto-apply or invent lights. Bind them to an audited scene rig and approve a native 4K pilot first.')
        lighting_warning.setWordWrap(True)
        lighting_layout.addWidget(lighting_warning)
        layout.addWidget(lighting_group)
        self.update_lighting_recipe()

        analysis_group = QtWidgets.QGroupBox('AI analysis')
        analysis_layout = QtWidgets.QFormLayout(analysis_group)
        self.analysis_provider = QtWidgets.QComboBox()
        self.analysis_provider.addItem('ChatGPT via Codex login', 'codex')
        self.analysis_provider.addItem('Omega Plus Vision', 'omega')
        provider_index = self.analysis_provider.findData(self.preferences['analysisProvider'])
        self.analysis_provider.setCurrentIndex(max(0, provider_index))
        analysis_layout.addRow('Provider', self.analysis_provider)
        self.analyze_button = QtWidgets.QPushButton('Analyze downloaded video against native V-Ray')
        self.analyze_button.clicked.connect(self.analyze)
        analysis_layout.addRow(self.analyze_button)
        analysis_note = QtWidgets.QLabel('Uses matched comparison frames. Analysis does not prove shader, UV, texture, geometry, or render-element identity.')
        analysis_note.setWordWrap(True)
        analysis_layout.addRow(analysis_note)
        layout.addWidget(analysis_group)

        settings_group = QtWidgets.QGroupBox('Settings · authentication and providers')
        settings_layout = QtWidgets.QFormLayout(settings_group)
        self.codex_status = QtWidgets.QLabel('Not checked')
        self.codex_status.setWordWrap(True)
        codex_row = QtWidgets.QWidget()
        codex_buttons = QtWidgets.QHBoxLayout(codex_row)
        codex_buttons.setContentsMargins(0, 0, 0, 0)
        codex_check = QtWidgets.QPushButton('Check ChatGPT login')
        codex_login = QtWidgets.QPushButton('Sign in')
        codex_check.clicked.connect(self.check_codex)
        codex_login.clicked.connect(self.login_codex)
        codex_buttons.addWidget(codex_check)
        codex_buttons.addWidget(codex_login)
        settings_layout.addRow('ChatGPT / Codex', self.codex_status)
        settings_layout.addRow('', codex_row)

        self.runway_name = QtWidgets.QLineEdit(self.preferences['runwayServer'])
        self.runway_endpoint = QtWidgets.QLineEdit(self.preferences['runwayEndpoint'])
        self.runway_status = QtWidgets.QLabel('Not checked')
        self.runway_status.setWordWrap(True)
        runway_row = QtWidgets.QWidget()
        runway_buttons = QtWidgets.QHBoxLayout(runway_row)
        runway_buttons.setContentsMargins(0, 0, 0, 0)
        runway_check = QtWidgets.QPushButton('Check MCP')
        runway_login = QtWidgets.QPushButton('Configure / sign in')
        runway_check.clicked.connect(self.check_runway_mcp)
        runway_login.clicked.connect(self.login_runway_mcp)
        runway_buttons.addWidget(runway_check)
        runway_buttons.addWidget(runway_login)
        settings_layout.addRow('Runway MCP name', self.runway_name)
        settings_layout.addRow('Runway MCP URL', self.runway_endpoint)
        settings_layout.addRow('Codex MCP status', self.runway_status)
        settings_layout.addRow('', runway_row)

        self.omega_model = QtWidgets.QComboBox()
        self.omega_model.setEditable(True)
        self.omega_model.addItems(OMEGA_MODELS)
        self.omega_model.setCurrentText(self.preferences['omegaModel'])
        self.omega_endpoint = QtWidgets.QLineEdit(self.preferences['omegaEndpoint'])
        self.omega_key = QtWidgets.QLineEdit()
        self.omega_key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.omega_key.setPlaceholderText('Stored in Windows Credential Manager')
        self.omega_status = QtWidgets.QLabel('Key stored' if self.credentials.read() else 'No key stored')
        omega_row = QtWidgets.QWidget()
        omega_buttons = QtWidgets.QHBoxLayout(omega_row)
        omega_buttons.setContentsMargins(0, 0, 0, 0)
        omega_save = QtWidgets.QPushButton('Save key securely')
        omega_clear = QtWidgets.QPushButton('Clear key')
        omega_test = QtWidgets.QPushButton('Test vision API')
        omega_save.clicked.connect(self.save_omega_key)
        omega_clear.clicked.connect(self.clear_omega_key)
        omega_test.clicked.connect(self.test_omega)
        omega_buttons.addWidget(omega_save)
        omega_buttons.addWidget(omega_clear)
        omega_buttons.addWidget(omega_test)
        settings_layout.addRow('Omega model', self.omega_model)
        settings_layout.addRow('Omega chat/vision URL', self.omega_endpoint)
        settings_layout.addRow('Omega API key', self.omega_key)
        settings_layout.addRow('Omega status', self.omega_status)
        settings_layout.addRow('', omega_row)
        omega_note = QtWidgets.QLabel('Omega documentation exposes vision input, not image generation. The plugin will not present it as a generator.')
        omega_note.setWordWrap(True)
        settings_layout.addRow(omega_note)
        layout.addWidget(settings_group)

        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(300)
        self.log.setMinimumHeight(130)
        layout.addWidget(self.log)
        self.mode.currentIndexChanged.connect(self.update_timing)
        self.first.valueChanged.connect(self.update_timing)
        self.last.valueChanged.connect(self.update_timing)
        self.anchor_count.valueChanged.connect(self.update_timing)
        self.refresh()
        self.resize(530, 940)

    def message(self, text):
        self.log.appendPlainText(str(text))

    def read_job(self):
        return json.loads(self.job_path.read_text(encoding='utf-8')) if self.job_path else {}

    def refresh(self):
        try:
            self.camera.clear()
            for camera in native.cameras():
                self.camera.addItem(str(camera.name), int(rt.getHandleByAnim(camera)))
            self.message('Production renderer: ' + native.renderer_name())
            self.update_timing()
        except Exception as exc:
            self.message(exc)

    def update_timing(self, *_):
        is_image = self.mode.currentData() == 'image'
        is_guided = self.mode.currentData() == 'guided'
        self.last.setEnabled(not is_image)
        self.duration.setEnabled(is_image)
        self.anchor_count.setEnabled(is_guided)
        self.loop_shot.setEnabled(is_guided)
        self.prompt.setEnabled(self.mode.currentData() != 'native')
        count = max(0, self.last.value() - self.first.value() + 1)
        if is_guided:
            seconds = max(0, self.last.value() - self.first.value()) / rt.frameRate
            self.timing.setText('%g fps · %d camera poses · %.3f-second keyed span · %d sparse 4K anchors. Use whole 4–15 seconds; e.g. 0–240 at 24 fps.' %
                                (rt.frameRate, count, seconds, self.anchor_count.value()))
            self.export_button.setText('1. Render full-rate 640×360 V-Ray guide + sparse native 4K anchors')
        else:
            self.timing.setText('%g fps · %d sequence frames · %.3f seconds. AI sequence input: 4–15 whole seconds.' %
                                (rt.frameRate, count, count / rt.frameRate))
            self.export_button.setText('1. Render native reference at 3840 × 2160')
        self.update_actions()

    def update_actions(self, *_):
        busy = self.rendering or (self.process is not None and self.process.state() != QtCore.QProcess.NotRunning)
        for control in (self.export_button, self.connect_button, self.load_button, self.refresh_button):
            control.setEnabled(not busy)
        self.stop_button.setEnabled(self.rendering)
        job = self.read_job()
        self.preview_button.setEnabled(not busy and bool(job.get('source')))
        self.result_button.setEnabled(bool(self.job_path))
        self.analyze_button.setEnabled(not busy and bool(job.get('output')) and job.get('status') in ('complete', 'needs_review'))
        resumable = bool(job.get('taskId')) and job.get('status') not in ('complete', 'needs_review', 'remote_failed')
        self.submit_button.setText('Resume saved Runway task' if resumable else '3. Send to Runway · creates a paid 4K generation')
        self.submit_button.setEnabled(not busy and (resumable or (job.get('status') == 'ready' and self.reviewed.isChecked())))

    def choose_output(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, 'Choose job folder', self.output.text())
        if folder:
            self.output.setText(folder)

    def stop_render(self):
        self.stop_requested = True
        self.message('Stopping after the current frame. Use Esc to cancel inside V-Ray.')

    def export(self):
        try:
            native.preflight()
            handle = self.camera.currentData()
            camera = rt.getAnimByHandle(handle) if handle is not None else None
            if camera is None:
                raise RuntimeError('Choose a valid camera.')
            self.job_path, job = create_job(self.output.text(), camera.name,
                self.first.value(), self.last.value(), int(rt.frameRate), self.mode.currentData(),
                self.prompt.toPlainText(), self.duration.value(), self.anchor_count.value(),
                self.loop_shot.isChecked())
            self.reviewed.setChecked(False)
            self.rendering = True
            self.stop_requested = False
            self.update_actions()
            def progress(index, count, frame):
                guide_count = self.last.value() - self.first.value() + 1
                stage = 'Guide' if job['mode'] == 'guided' and index < guide_count else '4K anchor' if job['mode'] == 'guided' else 'Frame'
                self.message('%s %d (%d/%d)...' % (stage, frame, index + 1, count))
                QtWidgets.QApplication.processEvents()
            native.render_job(self.job_path, job, camera, progress, lambda: self.stop_requested)
            self.message('V-Ray export complete. Preparing review media...')
        except Exception as exc:
            self.message('Export stopped: ' + str(exc))
            return
        finally:
            self.rendering = False
            self.update_actions()
        self.start_bridge('prepare', self.job_path)

    def start_bridge(self, action, filename=None, extra=None, environment=None):
        if self.process is not None and self.process.state() != QtCore.QProcess.NotRunning:
            return
        node = shutil.which('node') or r'C:\Program Files\nodejs\node.exe'
        if not Path(node).is_file():
            self.message('Node.js 20.19+ is required. Install Node, then run Setup.ps1.')
            return
        if not (ROOT / 'bridge/node_modules/mcp-remote/dist/proxy.js').is_file():
            self.message('Run Setup.ps1 in the plugin folder to install the Runway companion.')
            return
        self.process = QtCore.QProcess(self)
        self.process_action = action
        self.process.setProgram(node)
        args = [str(ROOT / 'bridge/cli.mjs'), action]
        if filename:
            args.append(str(filename))
        if extra:
            args.append(str(extra))
        self.process.setArguments(args)
        self.process.setWorkingDirectory(str(ROOT / 'bridge'))
        if environment:
            process_environment = QtCore.QProcessEnvironment.systemEnvironment()
            for key, value in environment.items():
                process_environment.insert(str(key), str(value))
            self.process.setProcessEnvironment(process_environment)
        self.stdout_buffer = ''
        self.stderr_buffer = ''
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(self.drain_errors)
        self.process.finished.connect(self.bridge_finished)
        self.process.errorOccurred.connect(lambda error: self.message('Companion process error: ' + str(error)))
        self.process.start()
        self.message('Starting ' + action + '...')
        self.update_actions()

    def read_output(self):
        self.stdout_buffer += bytes(self.process.readAllStandardOutput()).decode('utf-8', errors='replace')
        while '\n' in self.stdout_buffer:
            line, self.stdout_buffer = self.stdout_buffer.split('\n', 1)
            try:
                self.message(json.loads(line)['message'])
            except (ValueError, KeyError):
                pass

    def drain_errors(self):
        # Child diagnostics are retained only in memory; don't print signed URLs/tokens.
        self.stderr_buffer = (self.stderr_buffer + bytes(self.process.readAllStandardError()).decode('utf-8', errors='replace'))[-4000:]

    def bridge_finished(self, code, _status):
        self.read_output()
        self.message('Companion finished.' if code == 0 else 'Companion stopped. See the error above; saved task IDs can be resumed.')
        if code == 0 and self.process_action == 'analyze':
            result = self.read_job().get('aiAnalysis', {})
            self.message('Final QC gate: ' + str(result.get('finalGate', 'unavailable')))
        self.process_action = None
        self.update_actions()

    def current_preferences(self):
        return {
            'analysisProvider': self.analysis_provider.currentData(),
            'runwayServer': self.runway_name.text(),
            'runwayEndpoint': self.runway_endpoint.text(),
            'omegaEndpoint': self.omega_endpoint.text(),
            'omegaModel': self.omega_model.currentText(),
        }

    def save_preferences(self):
        self.preferences = save_settings(self.current_preferences())
        return self.preferences

    def check_codex(self):
        try:
            code, text = run_codex(['login', 'status'])
            self.codex_status.setText(text if code == 0 else 'Not signed in: ' + text)
            self.message('ChatGPT/Codex status checked.')
        except Exception as exc:
            self.codex_status.setText(str(exc))

    def login_codex(self):
        try:
            launch_codex(['login'])
            self.codex_status.setText('Complete the supported Codex sign-in in the new window, then click Check.')
        except Exception as exc:
            self.codex_status.setText(str(exc))

    def check_runway_mcp(self):
        try:
            preferences = self.save_preferences()
            code, text = run_codex(['mcp', 'get', preferences['runwayServer'], '--json'])
            self.runway_status.setText('Configured in Codex.' if code == 0 else 'Not configured in Codex.')
            self.message('Runway MCP status checked.' if code == 0 else 'Runway MCP is not configured yet.')
        except Exception as exc:
            self.runway_status.setText(str(exc))

    def login_runway_mcp(self):
        try:
            preferences = self.save_preferences()
            name = preferences['runwayServer']
            code, _ = run_codex(['mcp', 'get', name, '--json'])
            if code != 0:
                code, text = run_codex(['mcp', 'add', name, '--url', preferences['runwayEndpoint']], timeout=30)
                if code != 0:
                    raise RuntimeError('Could not configure Runway MCP: ' + text)
            launch_codex(['mcp', 'login', name])
            self.runway_status.setText('Complete Runway authorization in the new window, then click Check MCP.')
        except Exception as exc:
            self.runway_status.setText(str(exc))

    def save_omega_key(self):
        try:
            self.credentials.write(self.omega_key.text())
            self.omega_key.clear()
            self.omega_status.setText('Key stored in Windows Credential Manager')
        except Exception as exc:
            self.omega_status.setText(str(exc))

    def clear_omega_key(self):
        try:
            self.credentials.delete()
            self.omega_key.clear()
            self.omega_status.setText('No key stored')
        except Exception as exc:
            self.omega_status.setText(str(exc))

    def analysis_environment(self, include_omega=False):
        environment = {'MAXRUNWAY_ANALYSIS_SETTINGS': json.dumps(self.save_preferences())}
        executable = codex_path()
        if executable:
            environment['CODEX_CLI_PATH'] = executable
        if include_omega:
            key = self.credentials.read()
            if not key:
                raise RuntimeError('Save an Omega Plus API key first.')
            environment['OMEGAPLUS_API_KEY'] = key
        return environment

    def test_omega(self):
        try:
            preferences = self.save_preferences()
            environment = self.analysis_environment(include_omega=True)
            self.start_bridge('omega-test', json.dumps({
                'omegaEndpoint': preferences['omegaEndpoint'],
                'omegaModel': preferences['omegaModel'],
            }), environment=environment)
        except Exception as exc:
            self.omega_status.setText(str(exc))

    def analyze(self):
        try:
            provider = self.analysis_provider.currentData()
            environment = self.analysis_environment(include_omega=provider == 'omega')
            if provider == 'codex':
                code, text = run_codex(['login', 'status'])
                if code != 0:
                    raise RuntimeError('Sign in to ChatGPT/Codex first: ' + text)
            self.start_bridge('analyze', self.job_path, provider, environment)
        except Exception as exc:
            self.message('Analysis stopped: ' + str(exc))

    def open_reference(self):
        source = self.read_job().get('source')
        if source:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(source))

    def open_result(self):
        if self.job_path:
            destination = self.read_job().get('output') or str(self.job_path.parent)
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(destination))

    def update_lighting_recipe(self, *_):
        recipe = self.lighting_recipe.currentData()
        if not recipe:
            self.lighting_details.setPlainText('No recipe is available.')
            return
        starts = []
        for key, value in recipe.get('settings', {}).items():
            if isinstance(value, dict) and 'start' in value:
                starts.append('%s: %s' % (key.replace('_', ' '), value['start']))
            elif value is not None and not isinstance(value, (dict, list)):
                starts.append('%s: %s' % (key.replace('_', ' '), value))
        self.lighting_details.setPlainText('%s\n\nEligibility: %s\nGrade: %s\nStarting guidance: %s' % (
            recipe.get('purpose', ''), recipe.get('eligibility', ''),
            recipe.get('grade_pair', ''), ', '.join(starts) or 'scene audit required'))

    def open_lighting_guide(self):
        guide = ROOT / 'presets/IMPACT-Inspired-Lighting-Presets.md'
        if guide.is_file():
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(guide)))
        else:
            self.message('Lighting guide is missing from this package.')

    def load_job(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Load exported job', self.output.text(), 'Job (job.json)')
        if not filename:
            return
        try:
            data = json.loads(Path(filename).read_text(encoding='utf-8'))
            if data.get('schemaVersion') != 1:
                raise ValueError('Unsupported job version.')
            self.job_path = Path(filename)
            self.reviewed.setChecked(False)
            self.message('Loaded job: ' + data['status'])
            if data['status'] == 'rendered':
                self.start_bridge('prepare', self.job_path)
            self.update_actions()
        except Exception as exc:
            self.message(exc)

    def closeEvent(self, event):
        # Hiding preserves live render/companion ownership, avoiding orphaned jobs.
        self.hide()
        event.ignore()


def show():
    global _panel
    if _panel is None:
        parent = GetQMaxMainWindow()
        _panel = Panel(parent)
        parent.addDockWidget(QtCore.Qt.RightDockWidgetArea, _panel)
        _panel.setFloating(True)
    _panel.show()
    _panel.raise_()
    return _panel
