#   Copyright 2014-present PUNCH Cyber Analytics Group
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""
Overview
========

Handle file and directory interactions

"""

import os
import hashlib
from pathlib import Path
from asyncio import Queue
from datetime import datetime
from typing import Dict, Optional

from stoq import helpers
from stoq.helpers import StoqConfigParser
from stoq.exceptions import StoqPluginException
from stoq.plugins import ProviderPlugin, ConnectorPlugin, ArchiverPlugin
from stoq import Payload, PayloadMeta, ArchiverResponse, StoqResponse, Request


class FileDirPlugin(ProviderPlugin, ConnectorPlugin, ArchiverPlugin):
    def __init__(self, config: StoqConfigParser) -> None:
        super().__init__(config)

        self.source_dir = config.get('options', 'source_dir', fallback=None)
        self.recursive = config.getboolean('options', 'recursive', fallback=False)
        self.results_dir = config.get(
            'options', 'results_dir', fallback=os.path.join(os.getcwd(), 'results')
        )
        self.date_mode = config.getboolean('options', 'date_mode', fallback=False)
        self.date_format = config.get('options', 'date_format', fallback='%Y/%m/%d')
        self.compactly = config.getboolean('options', 'compactly', fallback=True)
        self.archive_dir = config.get(
            'options', 'archive_dir', fallback=os.path.join(os.getcwd(), 'archive')
        )
        self.use_sha = config.getboolean('options', 'use_sha', fallback=True)

    async def ingest(self, queue: Queue) -> None:
        """
        Ingest files from a directory

        """
        if not self.source_dir:
            raise StoqPluginException('Source directory not defined')
        if os.path.isdir(self.source_dir):
            if self.recursive:
                for root_path, subdirs, files in os.walk(self.source_dir):
                    for entry in files:
                        path = os.path.join(root_path, entry)
                        await self._queue(path, queue)
            else:
                for entry in os.scandir(self.source_dir):
                    if not entry.name.startswith('.') and entry.is_file():
                        path = os.path.join(self.source_dir, entry.name)
                        await self._queue(path, queue)
        elif os.path.isfile(self.source_dir):
            await self._queue(self.source_dir, queue)

    async def _queue(self, path: str, queue: Queue) -> None:
        """
        Publish payload to stoQ queue

        """
        meta = PayloadMeta(
            extra_data={
                'filename': os.path.basename(path),
                'source_dir': os.path.dirname(path),
            }
        )
        with open(path, "rb") as f:
            await queue.put(Payload(f.read(), meta))

    async def save(self, response: StoqResponse) -> None:
        """
        Save results to disk

        """

        path = self.results_dir
        filename = response.scan_id
        if self.date_mode:
            now = datetime.now().strftime(self.date_format)
            path = f'{path}/{now}'
        path = os.path.abspath(path)
        Path(path).mkdir(parents=True, exist_ok=True)
        with open(f'{path}/{filename}', 'x') as outfile:
            outfile.write(f'{helpers.dumps(response, compactly=self.compactly)}\n')

    async def archive(self, payload: Payload, request: Request) -> ArchiverResponse:
        """
        Archive payload to disk

        """
        path = self.archive_dir
        filename = payload.results.payload_id
        if self.use_sha:
            filename = hashlib.sha1(payload.content).hexdigest()
            path = f'{path}/{"/".join(list(filename[:5]))}'
        elif self.date_mode:
            now = datetime.now().strftime(self.date_format)
            path = f'{path}/{now}'
        path = os.path.abspath(path)
        Path(path).mkdir(parents=True, exist_ok=True)
        try:
            with open(f'{path}/{filename}', 'xb') as outfile:
                outfile.write(payload.content)
        except FileExistsError:
            pass
        return ArchiverResponse({'path': f'{path}/{filename}'})

    async def get(self, task: ArchiverResponse) -> Payload:
        """
        Retrieve archived payload from disk

        """
        path = os.path.abspath(task.results['path'])
        meta = PayloadMeta(extra_data=task.results)
        with open(path, 'rb') as f:
            return Payload(f.read(), meta)
