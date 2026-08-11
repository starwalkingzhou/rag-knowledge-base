import {useState} from 'react'
import {
    App,
    Button,
    Form,
    Input,
    Modal,
    Popconfirm,
    Table,
    Tag,
} from 'antd'
import {DeleteOutlined, EditOutlined, PlusOutlined} from '@ant-design/icons'
import type {ColumnsType} from 'antd/es/table'

import {PermissionTagsField} from '@/components/PermissionTagsField'
import {
    useCreateRoleMutation,
    useDeleteRoleMutation,
    useRoles,
    useUpdateRoleMutation,
} from '@/api/roles'
import type {RoleRead} from '@/client/types.gen'

interface CreateFormValues {
    name: string
    description: string
    permission_tags: string[]
}

interface EditFormValues {
    description: string
    permission_tags: string[]
}

function CreateRoleModal({
                            open,
                            onClose,
                        }: {
    open: boolean
    onClose: () => void
}) {
    const {message} = App.useApp()
    const createMutation = useCreateRoleMutation()
    const [form] = Form.useForm<CreateFormValues>()

    return (
        <Modal
            title="新建角色"
            open={open}
            onCancel={() => {
                form.resetFields()
                onClose()
            }}
            destroyOnHidden
            onOk={async () => {
                const values = await form.validateFields()
                await createMutation.mutateAsync(values)
                message.success('角色已创建')
                form.resetFields()
                onClose()
            }}
            confirmLoading={createMutation.isPending}
            okText="创建"
        >
            <Form
                form={form}
                layout="vertical"
                initialValues={{permission_tags: []}}
            >
                <Form.Item
                    name="name"
                    label="角色名"
                    rules={[
                        {required: true, message: '请输入角色名'},
                        {pattern: /^[a-z][a-z0-9_]*$/, message: '仅支持小写字母/数字/下划线'},
                    ]}
                >
                    <Input placeholder="如: editor, auditor" autoFocus/>
                </Form.Item>
                <Form.Item name="description" label="描述">
                    <Input.TextArea rows={2} placeholder="角色描述"/>
                </Form.Item>
                <Form.Item name="permission_tags" label="权限标签">
                    <PermissionTagsField/>
                </Form.Item>
            </Form>
        </Modal>
    )
}

function EditRoleModal({
                           open,
                           onClose,
                           target,
                       }: {
    open: boolean
    onClose: () => void
    target: RoleRead | null
}) {
    const {message} = App.useApp()
    const updateMutation = useUpdateRoleMutation()
    const [form] = Form.useForm<EditFormValues>()

    async function onFinish(values: EditFormValues) {
        if (!target) return
        try {
            await updateMutation.mutateAsync({
                roleId: target.id,
                payload: {
                    description: values.description,
                    permission_tags: values.permission_tags,
                },
            })
            message.success('已保存')
            form.resetFields()
            onClose()
        } catch {
            // 拦截器已弹错误
        }
    }

    return (
        <Modal
            title={`编辑角色 ${target?.name ?? ''}`}
            open={open}
            onCancel={() => {
                form.resetFields()
                onClose()
            }}
            destroyOnHidden
            onOk={() => {
                void form.submit()
            }}
            confirmLoading={updateMutation.isPending}
            okText="保存"
        >
            <Form
                form={form}
                layout="vertical"
                initialValues={{
                    description: target?.description ?? '',
                    permission_tags: target?.permission_tags ?? [],
                }}
                onFinish={onFinish}
            >
                <Form.Item label="角色名">
                    <Input value={target?.name} disabled/>
                </Form.Item>
                <Form.Item name="description" label="描述">
                    <Input.TextArea rows={2} placeholder="角色描述"/>
                </Form.Item>
                <Form.Item name="permission_tags" label="权限标签">
                    <PermissionTagsField/>
                </Form.Item>
            </Form>
        </Modal>
    )
}

function DeleteRoleButton({
                              roleId,
                              roleName,
                          }: {
    roleId: string
    roleName: string
}) {
    const {message} = App.useApp()
    const mutation = useDeleteRoleMutation()
    return (
        <Popconfirm
            title={`删除角色 "${roleName}"?`}
            description="删除后已分配该角色的用户将失去对应权限"
            okType="danger"
            onConfirm={async () => {
                try {
                    await mutation.mutateAsync(roleId)
                    message.success('已删除')
                } catch {
                    // 拦截器已弹错误
                }
            }}
        >
            <Button size="small" danger icon={<DeleteOutlined/>}>
                删除
            </Button>
        </Popconfirm>
    )
}

export function RolesPage() {
    const {data, isLoading} = useRoles()
    const [createOpen, setCreateOpen] = useState(false)
    const [editTarget, setEditTarget] = useState<RoleRead | null>(null)

    const columns: ColumnsType<RoleRead> = [
        {title: '角色名', dataIndex: 'name', width: 140},
        {
            title: '描述',
            dataIndex: 'description',
            width: 200,
            render: (v: string) => v || '—',
        },
        {
            title: '权限标签',
            dataIndex: 'permission_tags',
            width: 280,
            render: (tags: string[] | undefined) => (
                <span>
                    {(tags ?? []).map(t => (
                        <Tag key={t}>{t}</Tag>
                    ))}
                    {!tags || tags.length === 0 ? <Tag color="default">公开</Tag> : null}
                </span>
            ),
        },
        {
            title: '创建时间',
            dataIndex: 'created_at',
            width: 160,
            render: (v: string) => new Date(v).toLocaleString(),
        },
        {
            title: '操作',
            width: 140,
            render: (_, record) => (
                <span>
                    <Button
                        size="small"
                        icon={<EditOutlined/>}
                        style={{marginRight: 8}}
                        onClick={() => setEditTarget(record)}
                    >
                        编辑
                    </Button>
                    <DeleteRoleButton
                        roleId={record.id}
                        roleName={record.name}
                    />
                </span>
            ),
        },
    ]

    return (
        <div>
            <div style={{marginBottom: 16, display: 'flex', justifyContent: 'space-between'}}>
                <h2 style={{margin: 0}}>角色管理</h2>
                <Button
                    type="primary"
                    icon={<PlusOutlined/>}
                    onClick={() => setCreateOpen(true)}
                >
                    新建角色
                </Button>
            </div>
            <Table
                rowKey="id"
                loading={isLoading}
                columns={columns}
                dataSource={data ?? []}
                pagination={false}
            />
            <CreateRoleModal
                open={createOpen}
                onClose={() => setCreateOpen(false)}
            />
            <EditRoleModal
                open={editTarget !== null}
                onClose={() => setEditTarget(null)}
                target={editTarget}
            />
        </div>
    )
}
